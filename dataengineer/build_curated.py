"""
DE3 -- Build curated tables from staging, as a runnable script rather than
only living inside de3.ipynb (which had two inconsistent copies of
build_curated_tables using different column names -- contract_key in one
version, contract_id in the other). This is the single reconciled version.

It also fixes a real, previously-silent bug: the notebook wrote the churn
column into fact_customer_account as `churn`, but churn_service.py's primary
query reads `f.churn_flag` -- so that query always raised, and
get_churn_summary()/get_high_risk_customers() were always falling back to
scanning stg_customer_raw. This script names the column churn_flag so the
curated-table code path actually runs.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from customer_cleaner import CustomerCleaner  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def clean_staging(engine: Engine, source_table: str = "stg_customer_raw") -> pd.DataFrame:
    df = pd.read_sql(f"SELECT * FROM {source_table}", con=engine)
    cleaned_df = CustomerCleaner(df).clean()
    cleaned_df.to_sql("cleaned_customers", con=engine, if_exists="replace", index=False)
    logger.info("clean_staging: read %s rows, wrote %s rows", len(df), len(cleaned_df))
    return cleaned_df


def build_curated_tables(cleaned_df: pd.DataFrame, engine: Engine) -> dict:
    with engine.begin() as conn:
        conn.execute(text(
            """CREATE TABLE IF NOT EXISTS dim_contract (
                contract_id INT AUTO_INCREMENT PRIMARY KEY,
                contract_type VARCHAR(30) UNIQUE NOT NULL
            )"""
        ))
        conn.execute(text(
            """CREATE TABLE IF NOT EXISTS dim_payment (
                payment_id INT AUTO_INCREMENT PRIMARY KEY,
                payment_method VARCHAR(50) UNIQUE NOT NULL
            )"""
        ))
        conn.execute(text(
            """CREATE TABLE IF NOT EXISTS fact_customer_account (
                customer_id VARCHAR(50) PRIMARY KEY,
                contract_id INT,
                payment_id INT,
                tenure INT,
                monthly_charges FLOAT,
                total_charges FLOAT,
                churn_flag INT,
                FOREIGN KEY (contract_id) REFERENCES dim_contract(contract_id),
                FOREIGN KEY (payment_id) REFERENCES dim_payment(payment_id)
            )"""
        ))
        conn.execute(text("TRUNCATE TABLE fact_customer_account"))
        conn.execute(text("DELETE FROM dim_contract"))
        conn.execute(text("ALTER TABLE dim_contract AUTO_INCREMENT = 1"))
        conn.execute(text("DELETE FROM dim_payment"))
        conn.execute(text("ALTER TABLE dim_payment AUTO_INCREMENT = 1"))

    dim_contract_data = cleaned_df[["contract"]].dropna().drop_duplicates().rename(
        columns={"contract": "contract_type"}
    )
    dim_contract_data.to_sql("dim_contract", con=engine, if_exists="append", index=False)

    dim_payment_data = cleaned_df[["payment_method"]].dropna().drop_duplicates()
    dim_payment_data.to_sql("dim_payment", con=engine, if_exists="append", index=False)

    contract_lookup = pd.read_sql("SELECT contract_id, contract_type FROM dim_contract", con=engine)
    payment_lookup = pd.read_sql("SELECT payment_id, payment_method FROM dim_payment", con=engine)

    fact_df = cleaned_df.merge(contract_lookup, left_on="contract", right_on="contract_type", how="left")
    fact_df = fact_df.merge(payment_lookup, on="payment_method", how="left")
    fact_df = fact_df.rename(columns={"churn": "churn_flag"})

    fact_data = fact_df[[
        "customer_id", "contract_id", "payment_id", "tenure",
        "monthly_charges", "total_charges", "churn_flag",
    ]]
    fact_data.to_sql("fact_customer_account", con=engine, if_exists="append", index=False)

    counts = {
        "dim_contract": len(dim_contract_data),
        "dim_payment": len(dim_payment_data),
        "fact_customer_account": len(fact_data),
    }
    logger.info("build_curated_tables: %s", counts)
    return counts


def quality_report(cleaned_df: pd.DataFrame) -> None:
    assert cleaned_df["customer_id"].isnull().sum() == 0, "FAIL: NULL values found in customer_id"
    logger.info("PASS: no NULL values in customer_id")

    assert cleaned_df["monthly_charges"].isnull().sum() == 0, "FAIL: NULL values found in monthly_charges"
    logger.info("PASS: no NULL values in monthly_charges")

    assert sorted(cleaned_df["churn"].unique().tolist()) == [0, 1], "FAIL: churn values are not 0 and 1"
    logger.info("PASS: churn values are 0 and 1")


def create_high_risk_view(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS v_high_risk_customers"))
        conn.execute(text(
            """
            CREATE VIEW v_high_risk_customers AS
            SELECT
                f.customer_id,
                f.tenure,
                f.monthly_charges,
                dc.contract_type,
                CONCAT(
                    'Month-to-month contract, tenure ', f.tenure, ' months, ',
                    'monthly charge $', f.monthly_charges, ' (above the ', 'average)'
                ) AS risk_reason
            FROM fact_customer_account f
            JOIN dim_contract dc ON f.contract_id = dc.contract_id
            WHERE dc.contract_type = 'Month-to-month'
              AND f.tenure < 12
              AND f.monthly_charges > (SELECT AVG(monthly_charges) FROM fact_customer_account)
            """
        ))
    logger.info("v_high_risk_customers view (re)created")


if __name__ == "__main__":
    from sqlalchemy import create_engine

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config import DATABASE_URL_PYMYSQL

    eng = create_engine(DATABASE_URL_PYMYSQL)
    cleaned = clean_staging(eng)
    build_curated_tables(cleaned, eng)
    quality_report(cleaned)
    create_high_risk_view(eng)
