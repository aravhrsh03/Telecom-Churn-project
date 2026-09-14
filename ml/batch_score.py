"""
Lab ML5 -- score every customer in batch, producing customer_risk_table.

Fixed a real portability bug here: this previously hardcoded
D:\\projectpart1\\telco2\\customer_ml_features.csv, a path from a different
machine/folder layout, so it could never have run on a fresh checkout.

Each run appends a dated snapshot to ml/risk_history/ (used by
pipeline/daily_brief.py, Lab AI4, to diff today vs. yesterday) as well as
writing the single current customer_risk_table.csv every other part of the
system reads.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from predict import predict_from_feature_row

BASE_DIR = Path(__file__).resolve().parent
FEATURES_CSV = BASE_DIR.parent / "customer_ml_features.csv"
RISK_TABLE_CSV = BASE_DIR / "customer_risk_table.csv"
RISK_HISTORY_DIR = BASE_DIR / "risk_history"


def score_all_customers() -> pd.DataFrame:
    df = pd.read_csv(FEATURES_CSV)
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")], errors="ignore")

    predictions = df.apply(lambda row: predict_from_feature_row(row.to_dict()), axis=1)
    df["risk_score"] = predictions.apply(lambda r: r["risk_score"])
    df["prediction"] = predictions.apply(lambda r: r["prediction"])
    df["confidence"] = predictions.apply(lambda r: r["confidence"])
    df["scoring_date"] = datetime.today().strftime("%Y-%m-%d")

    risk_table = df[["customer_id", "risk_score", "prediction", "confidence", "scoring_date"]]
    return risk_table


def main() -> pd.DataFrame:
    risk_table = score_all_customers()

    risk_table.to_csv(RISK_TABLE_CSV, index=False)

    RISK_HISTORY_DIR.mkdir(exist_ok=True)
    dated_path = RISK_HISTORY_DIR / f"{risk_table['scoring_date'].iloc[0]}.csv"
    risk_table.to_csv(dated_path, index=False)

    print("\nPrediction Summary")
    print(risk_table["prediction"].value_counts())

    print("\nTop 10 Highest Risk Customers")
    print(risk_table.sort_values(by="risk_score", ascending=False).head(10).to_string(index=False))

    print(f"\nWrote {RISK_TABLE_CSV} and {dated_path}")
    return risk_table


if __name__ == "__main__":
    main()
