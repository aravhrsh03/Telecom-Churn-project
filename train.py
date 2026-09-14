"""
Phase 7 Pre-Flight, Task 2 -- training as a runnable script.

Reproduces the model-training logic that previously only existed inside
ml/ml1.ipynb, so it can be run from a cold terminal:

    python train.py

It trains the same two models the notebook compared (Logistic Regression and
a depth-5 Decision Tree) on customer_ml_features.csv, prints the same
evaluation metrics, saves both models to ml/models/, and -- this is the
Lab CL1 fix -- persists everything predict.py needs to build a REAL feature
vector at inference time into ml/models/feature_columns.json:

  * the exact ordered training column list
  * the categorical columns that were one-hot encoded (so predict.py can
    build the same dummy column names)
  * the monthly_charges median used to compute high_charge_flag, so that
    derived feature can be recomputed identically at inference time instead
    of being hardcoded to 0
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.tree import DecisionTreeClassifier

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "customer_ml_features.csv"
MODELS_DIR = BASE_DIR / "ml" / "models"

TARGET_COL = "churn"
DROP_COLS = ["customer_id"]
# Every other categorical (object-dtype) column is one-hot encoded in a
# single pass -- this must stay identical to what predict.py assumes.
CATEGORICAL_COLS = [
    "gender", "multiple_lines", "internet_service", "online_security",
    "online_backup", "device_protection", "tech_support", "streaming_tv",
    "streaming_movies", "contract", "payment_method", "tenure_bucket",
]


def load_dataset() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")], errors="ignore")
    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, float]:
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    monthly_charges_median = float(df["monthly_charges"].median())

    y = df[TARGET_COL]
    X = df.drop(columns=[TARGET_COL])
    X = pd.get_dummies(X, columns=[c for c in CATEGORICAL_COLS if c in X.columns], drop_first=True)
    return X, y, monthly_charges_median


def main() -> None:
    print("Loading customer_ml_features.csv ...")
    df = load_dataset()
    X, y, monthly_charges_median = build_features(df)
    print(f"X shape: {X.shape}, y shape: {y.shape}")

    class_balance = y.value_counts(normalize=True).round(4)
    print("\nClass balance:")
    print(class_balance)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    log_reg = LogisticRegression(max_iter=1000)
    dtree = DecisionTreeClassifier(max_depth=5, random_state=42)

    log_reg.fit(X_train, y_train)
    dtree.fit(X_train, y_train)
    print("\nModels trained.")

    y_pred_lr = log_reg.predict(X_test)
    y_pred_dt = dtree.predict(X_test)

    print("\n=== Logistic Regression ===")
    print(classification_report(y_test, y_pred_lr, target_names=["Active", "Churned"]))
    print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred_lr))

    print("\n=== Decision Tree (max_depth=5) ===")
    print(classification_report(y_test, y_pred_dt, target_names=["Active", "Churned"]))
    print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred_dt))

    cv_f1_lr = cross_val_score(log_reg, X, y, cv=5, scoring="f1")
    cv_f1_dt = cross_val_score(dtree, X, y, cv=5, scoring="f1")

    results = pd.DataFrame({
        "Model": ["Logistic Regression", "Decision Tree"],
        "F1 (Churned, holdout)": [
            f1_score(y_test, y_pred_lr),
            f1_score(y_test, y_pred_dt),
        ],
        "CV F1 (mean)": [cv_f1_lr.mean(), cv_f1_dt.mean()],
    }).round(4)
    print("\nComparison:")
    print(results.to_string(index=False))

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(log_reg, MODELS_DIR / "logistic_churn.pkl")
    joblib.dump(dtree, MODELS_DIR / "tree_churn.pkl")
    print(f"\nModels saved to {MODELS_DIR}")

    feature_columns_meta = {
        "feature_columns": list(X.columns),
        "categorical_columns": CATEGORICAL_COLS,
        "monthly_charges_median": monthly_charges_median,
        "production_model_file": "logistic_churn.pkl",
        "trained_from": str(DATA_PATH.name),
        "notes": (
            "Written by train.py (Phase 7 Lab CL1). predict.py must read this file "
            "instead of guessing feature values -- see ml/predict.py."
        ),
    }
    with open(MODELS_DIR / "feature_columns.json", "w", encoding="utf-8") as f:
        json.dump(feature_columns_meta, f, indent=2)
    print(f"Wrote {MODELS_DIR / 'feature_columns.json'} "
          f"({len(feature_columns_meta['feature_columns'])} feature columns)")


if __name__ == "__main__":
    main()
