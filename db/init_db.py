"""
One-command, reproducible database setup -- closes the gap where dim/fact
tables and the v_high_risk_customers view only ever existed by hand in a live
MySQL instance. Run with:

    python db/init_db.py

Requires a running MySQL server reachable with the credentials in .env
(defaults to root/root@localhost, matching this project's previous hardcoded
values -- see config.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, DATABASE_URL_PYMYSQL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def create_database_if_missing() -> None:
    bootstrap_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
    bootstrap_engine = create_engine(bootstrap_url)
    with bootstrap_engine.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4"))
    bootstrap_engine.dispose()
    print(f"[1/5] Database `{DB_NAME}` ready")


def main() -> None:
    create_database_if_missing()

    from dataengineer import ingestion, build_curated

    engine = create_engine(DATABASE_URL_PYMYSQL)

    landing_csv = ROOT / "dataengineer" / "data" / "landing" / "customer_churn.csv"
    if not landing_csv.exists():
        raise FileNotFoundError(
            f"Expected the raw Telco CSV at {landing_csv}. Place customer_churn.csv there first."
        )

    results = ingestion.process_landing(engine)
    print("[2/5] Ingestion:", results)

    import sql_alc2
    sql_alc2.load_telco_data(csv_path=str(landing_csv))
    print("[3/5] Curated `customers` table (stg_telco_customer) loaded")

    cleaned = build_curated.clean_staging(engine)
    build_curated.build_curated_tables(cleaned, engine)
    build_curated.quality_report(cleaned)
    build_curated.create_high_risk_view(engine)
    print("[4/5] dim/fact tables + v_high_risk_customers view built")

    ml_features_csv = ROOT / "customer_ml_features.csv"
    ml_df = pd.read_csv(ml_features_csv)
    ml_df = ml_df.drop(columns=[c for c in ml_df.columns if c.startswith("Unnamed")], errors="ignore")
    ml_df.to_sql("customer_ml_features", con=engine, if_exists="replace", index=False)
    print(f"[5/5] customer_ml_features table loaded ({len(ml_df)} rows)")

    print("\nDatabase setup complete.")


if __name__ == "__main__":
    main()
