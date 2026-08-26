from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.types import VARCHAR

from tables3 import Base, Customer, CustomerRaw, IngestionLog, SessionLocal

engine=create_engine("mysql+mysqlconnector://root:root@localhost:3306/proj")
Session=sessionmaker(bind=engine)


def load_raw_staging(csv_path: str=r"D:\projectpart1\WA_Fn-UseC_-Telco-Customer-Churn.csv"):
    df=pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    Base.metadata.create_all(bind=engine)

    df.to_sql(
        name="stg_customer_raw",
        con=engine,
        if_exists="replace",
        index=False,
        dtype={col: VARCHAR(255) for col in df.columns},
    )

session=SessionLocal()
try:
    log=IngestionLog(
        source_file=r"D:\projectpart1\WA_Fn-UseC_-Telco-Customer-Churn.csv",
        loaded_at=datetime.now(),
        status="loaded",
    )
    session.add(log)
    session.commit()
finally:
    session.close()



def load_telco_data(csv_path: str=r"D:\projectpart1\WA_Fn-UseC_-Telco-Customer-Churn.csv"):
    df=load_raw_staging(csv_path)

    df=df.rename(columns={"customerID": "customer_id"})

    df["TotalCharges"]=pd.to_numeric(df["TotalCharges"].astype(str).str.strip(), errors="coerce")
    df.loc[df["TotalCharges"].isna() & (df["tenure"].astype(float)==0), "TotalCharges"]=df.loc[
        df["TotalCharges"].isna() & (df["tenure"].astype(float)==0), "MonthlyCharges"
    ]
    df["TotalCharges"]=df["TotalCharges"].fillna(0.0)

    for col in [
        "gender", "Partner", "Dependents", "PhoneService", "MultipleLines", "InternetService",
        "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
        "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod", "Churn"
    ]:
        if col in df.columns:
            df[col]=df[col].astype(str).str.strip()

    df["SeniorCitizen"]=df["SeniorCitizen"].astype(int)
    df["tenure"]=df["tenure"].astype(int)
    df["MonthlyCharges"]=df["MonthlyCharges"].astype(float)
    df["TotalCharges"]=df["TotalCharges"].astype(float)

    Base.metadata.create_all(bind=engine)

    session=Session()
    try:
        session.query(Customer).delete()
        for _, row in df.iterrows():
            customer=Customer(
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


if __name__=="__main__":
    load_telco_data()
