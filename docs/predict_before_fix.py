from pathlib import Path
import joblib
import pandas as pd

# -----------------------------
# Load model
# -----------------------------

BASE_DIR=Path(__file__).parent

model=joblib.load(
    BASE_DIR / "models" / "logistic_churn.pkl"
)

# Use the exact columns stored in the model
feature_columns=list(model.feature_names_in_)

# -----------------------------
# Preprocessing
# -----------------------------

def preprocess_input(
    tenure,
    monthly_charges,
    contract_type,
    service_count
):
    # Create empty row with ALL training columns
    row={col: 0 for col in feature_columns}

    # Numerical features
    if "tenure" in row:
        row["tenure"]=tenure

    if "monthly_charges" in row:
        row["monthly_charges"]=monthly_charges

    if "service_count" in row:
        row["service_count"]=service_count

    # Contract type dummy columns
    contract_column=f"contract_type_{contract_type}"

    if contract_column in row:
        row[contract_column]=1

    # Create dataframe in EXACT training order
    df=pd.DataFrame([row])

    df=df[feature_columns]

    return df


# -----------------------------
# Prediction
# -----------------------------

def predict_churn(
    tenure,
    monthly_charges,
    contract_type,
    service_count
):
    X=preprocess_input(
        tenure,
        monthly_charges,
        contract_type,
        service_count
    )

    prediction=model.predict(X)[0]

    risk_score=float(
        model.predict_proba(X)[0][1]
    )

    return {
        "risk_score": round(risk_score, 4),
        "prediction": (
            "Likely to churn"
            if prediction==1
            else "Unlikely to churn"
        ),
        "confidence": round(
            max(risk_score, 1 - risk_score),
            4
        )
    }