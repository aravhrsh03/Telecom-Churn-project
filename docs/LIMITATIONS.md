# Limitations — Retention Assistant

Written honestly per Lab AI5's requirement: what this assistant genuinely
cannot know, and what it should never be used for.

## What it cannot know

- **Why customers actually leave.** There is no exit-interview, survey, or
  free-text feedback data anywhere in this system. The assistant can state
  *correlations* the model or the rule-based view already encode (e.g.
  "month-to-month + short tenure + high charges" is `v_high_risk_customers`'s
  own rule) but cannot give a true causal reason for any individual
  customer's decision to leave.
- **Anything about the future.** There is no forecasting model in this
  system. "What will churn look like next quarter" has no tool that can
  answer it truthfully -- the assistant is instructed to refuse rather than
  extrapolate from the current snapshot.
- **Anything about competitors, pricing elsewhere, or the broader market.**
  Out of scope of the dataset entirely.
- **Customer satisfaction, NPS, or support-ticket history.** Not present in
  the IBM/Telco dataset this system is built on.
- **Anything about a customer who isn't in `customer_ml_features` /
  `stg_telco_customer`.** The assistant should report "not found," never
  fabricate a plausible-looking profile.

## What its predictions are and aren't

- `predict_churn(customer_id=...)` uses that customer's real, complete
  engineered feature row -- this is as good as the underlying model gets
  (see the model's own evaluation: F1 ≈ 0.57-0.58 for the churned class,
  meaning it's a genuinely useful signal, not a coin flip, but also not
  something to treat as certain for any one customer).
- `predict_churn(tenure=..., monthly_charges=..., contract_type=...,
  service_count=...)` (no `customer_id`) is a **hypothetical** estimate.
  Anything not derivable from those four fields is defaulted to a reference
  category and named in the response's `assumptions` list -- the assistant
  is instructed to always surface those assumptions, never present a
  hypothetical number as if it were exact.

## What this should never be used for

- **Any individual employment, credit, insurance, or similarly consequential
  decision about a real person.** This is a training/demo system built on a
  public benchmark dataset, not a vetted production risk model.
- **As the sole basis for contacting or not contacting a customer.** The
  rule-based `v_high_risk_customers` view and the ML model are two
  different, sometimes disagreeing signals (see `docs/cl1_before_after.md`
  for a case where they'd disagree) -- both are decision *support*, not a
  decision.
- **Anything requiring real-time data.** The database is only as fresh as
  the last time `pipeline/run_pipeline.py` (or the Airflow DAG) actually
  ran.

## Known system limitations (not assistant-specific)

- No per-user authorization model -- the FastAPI service uses a single
  shared `X-API-Key`, so `validate_tool_args()` checks argument *shape*,
  not whether the caller is allowed to look up a given customer_id. See
  `docs/cl2_memory_and_security.md`'s red-team notes.
- The evaluation harness's "factual accuracy" score (see
  `docs/ai5_evaluation_report.md`) is a numeric-grounding proxy -- it
  checks that numbers in a reply trace back to a real tool result, not
  full semantic correctness of the sentence around them. A reply could
  cite a real number in a misleading way and still score as "grounded."
