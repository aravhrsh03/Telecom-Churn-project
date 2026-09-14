from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends, Query
from churn_service import get_churn_summary, get_high_risk_customers, get_customer_features

from tables3 import Customer, CustomerCreate, CustomerResponse, CustomerUpdate, SessionLocal, init_db, ChurnPredictionRequest
from ml.predict import predict_churn as model_predict_churn
from api.assistant import ToolLoopExceeded, chat as assistant_chat

app=FastAPI(title="Telco Customer API")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from config import API_KEY

api_key_header=APIKeyHeader(name="X-API-Key", auto_error=False)




def check_api_key(api_key: str=Depends(api_key_header)):
    if api_key !=API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()


def startup_event():
    init_db()


@app.get("/")
def root():
    return {"message": "Telco customer API is running"}


@app.get("/customers", response_model=list[CustomerResponse])
def get_customers(db: Session=Depends(get_db)):
    return db.query(Customer).all()


@app.get("/customers/high-risk")
def high_risk_customers(
    db: Session=Depends(get_db),
    limit: int = Query(50, ge=1),
    min_tenure: Optional[int] = Query(None, ge=0),
    max_tenure: Optional[int] = Query(None, ge=0)
):
    result=get_high_risk_customers(db, limit=limit, min_tenure=min_tenure, max_tenure=max_tenure)
    return { "count": len(result), "items": result }


@app.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str, db: Session=Depends(get_db)):
    customer=db.query(Customer).filter(Customer.customer_id==customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(customer: CustomerCreate, db: Session=Depends(get_db), _: str=Depends(check_api_key)):
    existing=db.query(Customer).filter(Customer.customer_id==customer.customer_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Customer ID already exists")

    new_customer=Customer(**customer.model_dump())
    

    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    return new_customer


@app.patch("/customers/{customer_id}", response_model=CustomerResponse)
def update_customer(customer_id: str, customer: CustomerUpdate, db: Session=Depends(get_db), _: str=Depends(check_api_key)):
    existing_customer=db.query(Customer).filter(Customer.customer_id==customer_id).first()
    if not existing_customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_data=customer.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key !="customer_id":
            setattr(existing_customer, key, value)

    db.commit()
    db.refresh(existing_customer)
    return existing_customer


@app.delete("/customers/{customer_id}", response_model=CustomerResponse)
def delete_customer(customer_id: str, db: Session=Depends(get_db), _: str=Depends(check_api_key)):
    customer=db.query(Customer).filter(Customer.customer_id==customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.delete(customer)
    db.commit()
    return customer


@app.get("/customers/{customer_id}/features")
def customer_features(customer_id: str, db: Session=Depends(get_db)):
    features = get_customer_features(db, customer_id)
    if not features:
        raise HTTPException(status_code=404, detail="Customer not found")
    return features


@app.get("/churn/summary")
def churn_summary(db: Session=Depends(get_db)):
    return get_churn_summary(db)




@app.post("/predict-churn")
def predict_churn(payload: ChurnPredictionRequest):

    return model_predict_churn(
        tenure=payload.tenure,
        monthly_charges=payload.monthly_charges,
        contract_type=payload.contract_type,
        service_count=payload.service_count
    )


class AssistantChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []
    use_thinking: bool = False


@app.post("/assistant/chat")
def assistant_chat_endpoint(payload: AssistantChatRequest):
    try:
        return assistant_chat(payload.message, payload.history, use_thinking=payload.use_thinking)
    except ToolLoopExceeded as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        # e.g. ANTHROPIC_API_KEY not configured
        raise HTTPException(status_code=503, detail=str(e))