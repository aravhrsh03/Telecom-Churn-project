"""
Phase 7, Lab CL2 -- durable project memory.

The facts Claude should always know about this system, so every script that
calls the API doesn't have to re-explain the dataset from scratch (and can't
accidentally give a different explanation each time). Prepend CONTEXT to
every system prompt that touches this project.

Kept under 200 lines on purpose -- this is meant to be skimmed, not a wiki.
"""

CONTEXT = """\
## Business context
Telecom operator, retention analytics system. ~7,043 customers as of the
last full load. Baseline churn rate is 26.5% (Yes) / 73.5% (No) -- a mild
class imbalance. Never invent a customer, a number, or a churn reason that
isn't backed by a real query result.

## Dataset quirks (IBM/Telco Customer Churn, source: Kaggle)
- `TotalCharges` arrives as a string with ~11 blank rows -- those are
  customers with tenure=0 who haven't been billed yet. Cleaned data fills
  these with that customer's monthly_charges.
- `customerID` (raw) / `customer_id` (cleaned) is an identifier, never a
  model feature.
- Categorical Yes/No columns are cleaned to 1/0 for: partner, dependents,
  phone_service, paperless_billing, churn. Service columns
  (online_security, online_backup, device_protection, tech_support,
  streaming_tv, streaming_movies, multiple_lines) keep their original
  Yes/No/"No internet service"/"No phone service" text values.

## Engineered features (see customer_cleaner.py, train.py)
tenure_bucket (0-12/13-24/25-48/49-72), high_charge_flag (monthly_charges >
median, threshold persisted in ml/models/feature_columns.json),
service_count (count of the 6 Yes-valued service columns),
is_long_term_customer (tenure >= 24), has_streaming_bundle (both streaming
services), auto_pay_flag (payment_method contains "automatic").

## Database layout (MySQL, database `proj`)
- `stg_customer_raw` -- staging, exact CSV shape, all VARCHAR.
- `stg_telco_customer` (ORM class `Customer`) -- cleaned, typed customer
  table. This is what GET /customers/{id} reads.
- `dim_contract`, `dim_payment`, `fact_customer_account` -- curated star
  schema (churn column here is named `churn_flag`, not `churn`).
- `customer_ml_features` -- one row per customer, every engineered feature,
  used for ML training and for exact (non-hypothetical) predictions.
- `v_high_risk_customers` -- SQL view: month-to-month + tenure<12 +
  monthly_charges above the dataset average. Rule-based, not ML.
- `ingestion_log` -- one row per data load attempt (LOADED/REJECTED).

## The trained model (see train.py, ml/predict.py)
Logistic Regression, 38 features, trained on customer_ml_features.csv.
Evaluate on F1 for the churned class, never raw accuracy (predicting "No"
for everyone scores ~73% accuracy and is useless). Two ways to get a
prediction:
  - `predict_churn(customer_id=...)` -- exact: pulls the customer's real
    feature row. Use this whenever a customer_id is available.
  - `predict_churn(tenure=..., monthly_charges=..., contract_type=...,
    service_count=...)` -- hypothetical/what-if mode. Fields that can't be
    derived from those four are defaulted to the model's reference category
    and listed in the response's `assumptions` field. Always surface those
    assumptions if you use this mode -- never present a hypothetical
    prediction as if it were exact.

## API surface (main2.py) -- these are also the assistant's tools
- GET /customers/{id} -- one customer's profile, 404 if unknown.
- GET /customers/{id}/features -- full engineered feature row.
- GET /customers/high-risk?limit=&min_tenure=&max_tenure= -- rule-based list.
- GET /churn/summary -- totals, churn rate, breakdown by contract/internet.
- POST /predict-churn -- live model prediction (real or hypothetical).

## Ground rules for anything generated about this system
1. Never state a number that didn't come from a real query or tool result.
2. Cap any customer list at a small number (see
   config.ASSISTANT_MAX_LIST_ITEMS) -- never dump the whole table.
3. Never claim a causal reason for churn beyond what a tool result actually
   supports (e.g. "high risk because month-to-month + short tenure" is
   supported by v_high_risk_customers' own rule; a claim like "customers
   leave because of poor support" is not supported by anything in this
   system and must not be stated as fact).
4. If asked something no available tool can answer, say so plainly instead
   of guessing.
"""
