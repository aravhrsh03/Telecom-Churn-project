from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict,field_validator
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
#import field_validator
Base=declarative_base()


class Customer(Base):
    __tablename__="stg_telco_customer"

    customer_id=Column(String(50), primary_key=True)
    gender=Column(String(20), nullable=False)
    senior_citizen=Column(Integer, nullable=False)
    partner=Column(String(20), nullable=False)
    dependents=Column(String(20), nullable=False)
    tenure=Column(Integer, nullable=False)
    phone_service=Column(String(20), nullable=False)
    multiple_lines=Column(String(30), nullable=False)
    internet_service=Column(String(30), nullable=False)
    online_security=Column(String(30), nullable=False)
    online_backup=Column(String(30), nullable=False)
    device_protection=Column(String(30), nullable=False)
    tech_support=Column(String(30), nullable=False)
    streaming_tv=Column(String(30), nullable=False)
    streaming_movies=Column(String(30), nullable=False)
    contract=Column(String(30), nullable=False)
    paperless_billing=Column(String(20), nullable=False)
    payment_method=Column(String(50), nullable=False)
    monthly_charges=Column(Float, nullable=False)
    total_charges=Column(Float, nullable=False)
    churn=Column(String(10), nullable=False)


class CustomerRaw(Base):
    __tablename__="stg_customer_raw"

    customerID=Column(String(50), primary_key=True)
    gender=Column(String(50), nullable=False)
    SeniorCitizen=Column(String(20), nullable=False)
    Partner=Column(String(50), nullable=False)
    Dependents=Column(String(50), nullable=False)
    tenure=Column(String(20), nullable=False)
    PhoneService=Column(String(50), nullable=False)
    MultipleLines=Column(String(50), nullable=False)
    InternetService=Column(String(50), nullable=False)
    OnlineSecurity=Column(String(50), nullable=False)
    OnlineBackup=Column(String(50), nullable=False)
    DeviceProtection=Column(String(50), nullable=False)
    TechSupport=Column(String(50), nullable=False)
    StreamingTV=Column(String(50), nullable=False)
    StreamingMovies=Column(String(50), nullable=False)
    Contract=Column(String(50), nullable=False)
    PaperlessBilling=Column(String(50), nullable=False)
    PaymentMethod=Column(String(100), nullable=False)
    MonthlyCharges=Column(String(50), nullable=False)
    TotalCharges=Column(String(50), nullable=False)
    Churn=Column(String(20), nullable=False)


class IngestionLog(Base):
    __tablename__="ingestion_log"

    id=Column(Integer, primary_key=True, autoincrement=True)
    source_file=Column(String(255), nullable=False)
    loaded_at=Column(DateTime, server_default=func.now(), nullable=False)
    row_count=Column(Integer, nullable=False)
    distinct_customer_ids=Column(Integer, nullable=False)
    status=Column(String(50), nullable=False)


class CustomerCreate(BaseModel):
    customer_id: str
    gender: str
    senior_citizen: int
    partner: str
    dependents: str
    tenure: int
    phone_service: str
    multiple_lines: str
    internet_service: str
    online_security: str
    online_backup: str
    device_protection: str
    tech_support: str
    streaming_tv: str
    streaming_movies: str
    contract: str
    paperless_billing: str
    payment_method: str
    monthly_charges: float
    total_charges: float
    churn: str


class CustomerUpdate(BaseModel):
    customer_id: Optional[str]=None
    gender: Optional[str]=None
    senior_citizen: Optional[int]=None
    partner: Optional[str]=None
    dependents: Optional[str]=None
    tenure: Optional[int]=None
    phone_service: Optional[str]=None
    multiple_lines: Optional[str]=None
    internet_service: Optional[str]=None
    online_security: Optional[str]=None
    online_backup: Optional[str]=None
    device_protection: Optional[str]=None
    tech_support: Optional[str]=None
    streaming_tv: Optional[str]=None
    streaming_movies: Optional[str]=None
    contract: Optional[str]=None
    paperless_billing: Optional[str]=None
    payment_method: Optional[str]=None
    monthly_charges: Optional[float]=None
    total_charges: Optional[float]=None
    churn: Optional[str]=None


class CustomerResponse(BaseModel):
    customer_id: str
    gender: str
    senior_citizen: int
    partner: str
    dependents: str
    tenure: int
    phone_service: str
    multiple_lines: str
    internet_service: str
    online_security: str
    online_backup: str
    device_protection: str
    tech_support: str
    streaming_tv: str
    streaming_movies: str
    contract: str
    paperless_billing: str
    payment_method: str
    monthly_charges: float
    total_charges: float
    churn: str


class ErrorResponse(BaseModel):
    detail: str
    status_code: int

class ChurnPredictionRequest(BaseModel):
    tenure: int
    monthly_charges: float
    contract_type: str
    service_count: int
    @field_validator("tenure")
    @classmethod
    def validate_tenure(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("tenure must be between 0 and 100")
        return v

    @field_validator("monthly_charges")
    @classmethod
    def validate_monthly_charges(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("monthly_charges must be > 0")
        return v



    model_config=ConfigDict(from_attributes=True)


engine=create_engine("mysql+mysqlconnector://root:root@localhost:3306/proj")
SessionLocal=sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    Base.metadata.create_all(bind=engine)
