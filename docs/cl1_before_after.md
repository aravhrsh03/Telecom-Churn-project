# Lab CL1 — Before / After

## Table 1 — same hypothetical inputs, old model+logic vs. new model+logic

The "before" column replays the exact old `preprocess_input()` logic (zero
everywhere except tenure/monthly_charges/service_count/contract dummy)
against the model as it was pre-fix (`git show HEAD:ml/models/logistic_churn.pkl`,
before `train.py` regenerated it). The "after" column is the current
`ml/predict.py` in hypothetical mode (derives `is_long_term_customer` and
`high_charge_flag`, approximates `total_charges`, defaults the rest to the
documented reference category).

| Scenario | Before risk | Before prediction | After risk | After prediction |
|---|---:|---|---:|---|
| New month-to-month, high bill (tenure=2, $95) | 0.7136 | Likely to churn | 0.582 | Likely to churn |
| Long-tenure two-year, low bill (tenure=60, $40) | 0.0367 | Unlikely to churn | 0.0488 | Unlikely to churn |
| Mid-tenure one-year, avg bill (tenure=20, $65) | 0.3113 | Unlikely to churn | 0.303 | Unlikely to churn |

Scores moved (as expected, since more of the real feature vector is now
populated correctly) without flipping any of these three predictions --
which is itself evidence the model's core signal was never broken, only
under-fed. The next table shows a case where under-feeding it *does*
flip the answer.

## Table 2 — hypothetical guess vs. real customer lookup, same customer

Customer `7590-VHVEG` (tenure=1, $29.85/mo, Month-to-month, 1 service) is a
real row in `customer_ml_features`. Compare scoring them by guessing (the
only option before this fix) against looking up their real feature row (the
new `customer_id` path):

| Mode | Risk score | Prediction |
|---|---:|---|
| Hypothetical (4 fields only, rest defaulted) | 0.4578 | **Unlikely** to churn |
| Real customer lookup (`predict_churn(customer_id="7590-VHVEG")`) | 0.5646 | **Likely** to churn |

Same customer, opposite prediction. This is the concrete cost of the
original bug, and the reason the fix adds a real-lookup path rather than
only improving the guesses.

## Workflow note — chat vs. API

The first-pass review and the train.py-vs-predict.py comparison
(`docs/cl1_first_pass_review.md`) were done in chat: the questions were
exploratory, the answers didn't need to be machine-parseable, and getting
them was a one-time thing. `audit_defect.py` exists because the *same*
comparison needs to be re-runnable against a future predict.py change and
produce something a script (or a CI check) can act on -- forcing
`tool_choice` turns "does this look right" into a structured, diffable
`audit_findings.json` instead of a paragraph a human has to re-read.

## Git history for this lab

Two commits bracket the fix, per the lab's requirement:

1. `chore(cl1): audit predict.py's feature gap before applying a fix` --
   baseline commit, `predict.py` still has the original bug.
2. `fix(cl1): compute real engineered features in predict.py instead of
   hardcoding placeholders` -- the fix in this document.
