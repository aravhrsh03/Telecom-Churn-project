from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.types import VARCHAR

from config import DATABASE_URL
from tables3 import Base, Customer, IngestionLog, SessionLocal

DEFAULT_CSV_PATH = str(Path(__file__).resolve().parent / "dataengineer" / "data" / "landing" / "customer_churn.csv")

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def load_raw_staging(csv_path: str = DEFAULT_CSV_PATH) -> pd.DataFrame:
    """Load the CSV into stg_customer_raw exactly as received (all VARCHAR), and
    return the DataFrame so callers don't have to re-read the file."""
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    Base.metadata.create_all(bind=engine)

    df.to_sql(
        name="stg_customer_raw",
        con=engine,
        if_exists="replace",
        index=False,
        dtype={col: VARCHAR(255) for col in df.columns},
    )

    session = SessionLocal()
    try:
        log = IngestionLog(
            source_file=csv_path,
            loaded_at=datetime.now(),
            row_count=len(df),
            distinct_customer_ids=df["customerID"].nunique(),
            status="loaded",
        )
        session.add(log)
        session.commit()
    finally:
        session.close()

    return df


def load_telco_data(csv_path: str = DEFAULT_CSV_PATH) -> None:
    """Load + type-cast the CSV into the curated `Customer` table (stg_telco_customer)."""
    df = load_raw_staging(csv_path)

    df = df.rename(columns={"customerID": "customer_id"})

    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"].astype(str).str.strip(), errors="coerce")
    df["MonthlyCharges"] = df["MonthlyCharges"].astype(float)
    zero_tenure_blank = df["TotalCharges"].isna() & (df["tenure"].astype(float) == 0)
    df.loc[zero_tenure_blank, "TotalCharges"] = df.loc[zero_tenure_blank, "MonthlyCharges"]
    df["TotalCharges"] = df["TotalCharges"].fillna(0.0)

    for col in [
        "gender", "Partner", "Dependents", "PhoneService", "MultipleLines", "InternetService",
        "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
        "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod", "Churn",
    ]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df["SeniorCitizen"] = df["SeniorCitizen"].astype(int)
    df["tenure"] = df["tenure"].astype(int)
    df["MonthlyCharges"] = df["MonthlyCharges"].astype(float)
    df["TotalCharges"] = df["TotalCharges"].astype(float)

    Base.metadata.create_all(bind=engine)

    session = Session()
    try:
        session.query(Customer).delete()
        for _, row in df.iterrows():
            customer = Customer(
                customer_id=str(row["customer_id"]),
                gender=str(row["gender"]),
                senior_citizen=int(row["SeniorCitizen"]),
                partner=str(row["Partner"]),
                dependents=str(row["Dependents"]),
                tenure=int(row["tenure"]),
                phone_service=str(row["PhoneService"]),
                multiple_lines=str(row["MultipleLines"]),
                internet_service=str(row["InternetService"]),
                online_security=str(row["OnlineSecurity"]),
                online_backup=str(row["OnlineBackup"]),
                device_protection=str(row["DeviceProtection"]),
                tech_support=str(row["TechSupport"]),
                streaming_tv=str(row["StreamingTV"]),
                streaming_movies=str(row["StreamingMovies"]),
                contract=str(row["Contract"]),
                paperless_billing=str(row["PaperlessBilling"]),
                payment_method=str(row["PaymentMethod"]),
                monthly_charges=float(row["MonthlyCharges"]),
                total_charges=float(row["TotalCharges"]),
                churn=str(row["Churn"]),
            )
            session.add(customer)
        session.commit()
        print(f"Loaded {len(df)} records into {Customer.__tablename__}")
    finally:
        session.close()


if __name__ == "__main__":
    load_telco_data()
