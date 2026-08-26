import pandas as pd
from datetime import datetime
from predict import predict_churn

df = pd.read_csv(r"D:\projectpart1\telco2\customer_ml_features.csv")

predictions = df.apply(
    lambda row: predict_churn(
        tenure=row["tenure"],
        monthly_charges=row["monthly_charges"],
        contract_type=row["contract"],
        service_count=row["service_count"]
    ),
    axis=1
)

df["risk_score"] = predictions.apply(
    lambda x: x["risk_score"]
)

df["prediction"] = predictions.apply(
    lambda x: x["prediction"]
)

df["confidence"] = predictions.apply(
    lambda x: x["confidence"]
)

df["scoring_date"] = datetime.today().strftime(
    "%Y-%m-%d"
)

risk_table = df[
    [
        "customer_id",
        "risk_score",
        "prediction",
        "confidence",
        "scoring_date"
    ]
]

risk_table.to_csv(
    "customer_risk_table.csv",
    index=False
)

print("\nPrediction Summary")
print(
    risk_table["prediction"]
    .value_counts()
)

print("\nTop 10 Highest Risk Customers")
print(
    risk_table.sort_values(
        by="risk_score",
        ascending=False
    ).head(10)
)