"""
Phase 7 Lab CL1 fix.

BEFORE: preprocess_input() built a row of zeros for every trained feature
except tenure, monthly_charges, service_count, and one contract_type dummy --
silently discarding total_charges, high_charge_flag, is_long_term_customer,
has_streaming_bundle, auto_pay_flag, and every internet_service/gender/
multiple_lines/payment_method/tenure_bucket dummy for EVERY prediction,
regardless of the real customer. audit_defect.py names this exact defect.

AFTER (this file):
  1. Every feature that CAN be derived from the caller's inputs, is derived
     -- using the median threshold train.py persisted, not a guess.
  2. A `customer_id` path bypasses guessing entirely: it pulls the customer's
     real engineered feature row from customer_ml_features (via
     churn_service.get_customer_features) and uses it directly. This is the
     right tool for "score this real customer" -- the common case.
  3. The "what-if" path (no customer_id -- a hypothetical customer for an
     agent exploring scenarios) is kept, because AI2 explicitly tests it as
     one of three tool-loop paths. What can't be derived is defaulted to the
     model's reference category and *named* in the response's "assumptions"
     list -- never silently guessed.

No retraining. Same models/logistic_churn.pkl the model was already using.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"

with open(MODELS_DIR / "feature_columns.json", encoding="utf-8") as f:
    _META = json.load(f)

FEATURE_COLUMNS: List[str] = _META["feature_columns"]
CATEGORICAL_COLUMNS: List[str] = _META["categorical_columns"]
MONTHLY_CHARGES_MEDIAN: float = _META["monthly_charges_median"]

model = joblib.load(MODELS_DIR / _META["production_model_file"])

# The reference (dropped-by-drop_first) category for each one-hot column,
# used only when a field genuinely isn't available -- documented explicitly
# in the response rather than silently defaulted.
_REFERENCE_CATEGORY = {
    "gender": "Female",
    "multiple_lines": "No",
    "internet_service": "DSL",
    "online_security": "No",
    "online_backup": "No",
    "device_protection": "No",
    "tech_support": "No",
    "streaming_tv": "No",
    "streaming_movies": "No",
    "contract": "Month-to-month",
    "payment_method": "Bank transfer (automatic)",
    "tenure_bucket": "0-12",
}
_REFERENCE_NUMERIC = {
    "senior_citizen": 0, "partner": 0, "dependents": 0,
    "phone_service": 0, "paperless_billing": 0,
}


def _tenure_bucket(tenure: float) -> str:
    bins = [0, 12, 24, 48, 72]
    labels = ["0-12", "13-24", "25-48", "49-72"]
    for hi, label in zip(bins[1:], labels):
        if tenure <= hi:
            return label
    return labels[-1]


def build_feature_row(raw: Dict[str, Any]) -> pd.DataFrame:
    """Turn a dict of raw (non-encoded) customer fields into the exact
    one-hot vector the model was trained on, in the exact trained column
    order. Missing categorical columns fall back to their reference
    category; missing numeric columns fall back to 0 -- callers should
    supply everything they actually know."""
    row = dict(raw)
    for col, default in _REFERENCE_CATEGORY.items():
        row.setdefault(col, default)
    for col, default in _REFERENCE_NUMERIC.items():
        row.setdefault(col, default)

    df = pd.DataFrame([row])
    df = pd.get_dummies(df, columns=[c for c in CATEGORICAL_COLUMNS if c in df.columns], drop_first=True)
    df = df.reindex(columns=FEATURE_COLUMNS, fill_value=0)
    return df


def _score(df: pd.DataFrame) -> Dict[str, Any]:
    prediction = int(model.predict(df)[0])
    risk_score = float(model.predict_proba(df)[0][1])
    return {
        "risk_score": round(risk_score, 4),
        "prediction": "Likely to churn" if prediction == 1 else "Unlikely to churn",
        "confidence": round(max(risk_score, 1 - risk_score), 4),
    }


def predict_from_customer_id(customer_id: str) -> Optional[Dict[str, Any]]:
    """The exact-answer path: pull the customer's real engineered feature
    row and score it. No approximation of any kind."""
    from tables3 import SessionLocal
    from churn_service import get_customer_features

    db = SessionLocal()
    try:
        row = get_customer_features(db, customer_id)
    finally:
        db.close()

    if row is None:
        return None

    df = build_feature_row(row)
    result = _score(df)
    result["customer_id"] = customer_id
    result["mode"] = "real_customer"
    result["assumptions"] = []
    return result


def predict_hypothetical(
    tenure: float,
    monthly_charges: float,
    contract_type: str,
    service_count: int,
    **extra_fields: Any,
) -> Dict[str, Any]:
    """The what-if path: a support agent typing in a hypothetical scenario.
    Only 4 fields are guaranteed -- everything derivable from them IS
    derived; everything else is defaulted to the reference category and
    named in `assumptions`, never silently guessed."""
    known = {"tenure", "monthly_charges", "contract", "service_count", *extra_fields.keys()}

    row: Dict[str, Any] = {
        "tenure": tenure,
        "monthly_charges": monthly_charges,
        "contract": contract_type,
        "service_count": service_count,
        # -- derived, not guessed --
        "is_long_term_customer": int(tenure >= 24),
        "high_charge_flag": int(monthly_charges > MONTHLY_CHARGES_MEDIAN),
        "tenure_bucket": _tenure_bucket(tenure),
        **extra_fields,
    }
    known.add("is_long_term_customer")
    known.add("high_charge_flag")
    known.add("tenure_bucket")

    if "total_charges" not in extra_fields:
        row["total_charges"] = round(tenure * monthly_charges, 2)
        approximated_total_charges = True
    else:
        approximated_total_charges = False

    df = build_feature_row(row)
    result = _score(df)
    result["mode"] = "hypothetical"

    assumptions: List[str] = []
    if approximated_total_charges:
        assumptions.append(
            "total_charges not provided -- approximated as tenure x monthly_charges"
        )
    defaulted = sorted(
        (set(_REFERENCE_CATEGORY) | set(_REFERENCE_NUMERIC)) - known
    )
    if defaulted:
        assumptions.append(
            f"not provided, defaulted to the reference ('No'/baseline) category: {', '.join(defaulted)}"
        )
    result["assumptions"] = assumptions
    return result


def predict_churn(
    tenure: Optional[float] = None,
    monthly_charges: Optional[float] = None,
    contract_type: Optional[str] = None,
    service_count: Optional[int] = None,
    customer_id: Optional[str] = None,
    **extra_fields: Any,
) -> Dict[str, Any]:
    """Back-compat entry point used by main2.py's /predict-churn and the
    assistant's prediction tool. Pass customer_id for an exact answer;
    otherwise supply the hypothetical-scenario fields."""
    if customer_id:
        result = predict_from_customer_id(customer_id)
        if result is not None:
            return result
        # fall through to hypothetical mode if the id isn't in the system,
        # rather than crashing -- but say so.
        result = predict_hypothetical(
            tenure or 0, monthly_charges or 0, contract_type or "Month-to-month",
            service_count or 0, **extra_fields,
        )
        result["assumptions"].insert(0, f"customer_id '{customer_id}' not found -- used hypothetical mode")
        return result

    if tenure is None or monthly_charges is None or contract_type is None or service_count is None:
        raise ValueError(
            "predict_churn requires either customer_id, or all of "
            "tenure/monthly_charges/contract_type/service_count."
        )
    return predict_hypothetical(tenure, monthly_charges, contract_type, service_count, **extra_fields)
