# Customer Retention Intelligence System — Deep Dive

> A phase-by-phase study guide to the telecom churn system: every file, endpoint, and known gap, plus the planned Claude-powered Phases 7 and 8 (from `customer-churn-newpart.docx`).
>
> Generated from a direct read of the repository at `D:\telecom_churn\Telecom-Churn-project` plus both project Word documents. Re-check anything load-bearing before presenting it live.

**Legend:** ✅ Built & working · ⚠️ Built, with rough edges · 🔭 Planned (not started)

---

## Table of Contents

1. [Overview & Architecture](#overview--architecture)
2. [Phase 1 — Python Core](#phase-1--python-core-) ✅
3. [Phase 2 — Database Layer](#phase-2--database-layer-) ✅
4. [Phase 3 — FastAPI Backend](#phase-3--fastapi-backend-) ✅
5. [Phase 4 — React Dashboard](#phase-4--react-dashboard-) ✅
6. [Phase 5 — Data Engineering](#phase-5--data-engineering-) ⚠️
7. [Phase 6 — Machine Learning](#phase-6--machine-learning-) ⚠️
8. [Known Gaps](#known-gaps)
9. [Phase 7 — Extending the System with Claude](#phase-7--extending-the-system-with-claude-) 🔭
10. [Phase 8 — The Retention AI Assistant](#phase-8--the-retention-ai-assistant-) 🔭
11. [How It All Connects](#how-it-all-connects)

---

## Overview & Architecture

**The dataset.** Everything downstream is built on the **IBM/Telco Customer Churn** dataset — **7,043 customers**, **21 columns**, one row per customer representing a snapshot of their profile, subscriptions, billing, and whether they left. The baseline churn rate is **26.5% Yes / 73.5% No** — a mild imbalance that shows up again and again in how the models and metrics were chosen later.

**The shape of the system.** It's a straight pipeline with a fork at the end: clean the data once, load it into a proper relational schema, compute the same features twice (once for reporting, once for ML), train a model, and then serve everything — raw records, aggregates, rule-based risk, and live predictions — through one FastAPI service that both a React dashboard and (soon) a Claude assistant will call.

```
Phase 1        Phase 2       Phase 3      Phase 4      Phase 5          Phase 6       Phase 7          Phase 8
Python Core → Database    → FastAPI   → React UI   → Data Eng.      → ML Models  → Claude Harden → AI Assistant
  (CP1–CP5)     (SQL1–SQL6)  (API1–API6)  (RE1–RE5)   (DE1–DE8*)  ⚠️  (ML1–ML5*)⚠️   (CL1–CL2) 🔭     (AI1–AI5) 🔭
   ✅              ✅            ✅            ✅
```

| Layer | Where it lives | What it's for |
|---|---|---|
| Cleaning | `customer_cleaner.py` | One class, reused everywhere data needs to be trusted |
| Database | `tables3.py`, `sql_alc2.py`, MySQL `proj` schema | Staging + curated tables, ORM models, rule-based view |
| API | `main2.py`, `churn_service.py` | One FastAPI service exposing every capability as an endpoint |
| UI | `CustomerDashboard/` (React + Vite) | Support-agent and executive-facing dashboard |
| Pipeline | `dataengineer/` | Batch ingestion → clean → feature build → quality gate |
| ML | `ml/` | Trained models, live prediction, nightly batch scoring |
| AI layer 🔭 | — (Phase 7 & 8) | Claude audits the code, then becomes a tool-calling assistant on top of the API |

---

## Phase 1 — Python Core ✅

**Goal:** Turn a messy CRM export into a DataFrame every later phase can trust, without touching a database or a model yet.

**Files:** `customer_cleaner.py` · `customer_pipeline.py` · `customer_pipeline2.py` · `cleanercheck.ipynb` · `data_clean2.ipynb` · `outputs/*.csv`

The dataset's two real quality problems are: `TotalCharges` is stored as text and has 11 blank cells (customers with 0 months' tenure who haven't been billed yet), and every Yes/No column needs to become 1/0 before any model can use it. `customer_cleaner.py` exists to fix both, once, in a class every later phase imports rather than re-implementing.

### `CustomerCleaner` — method by method

| Method | What it does | Why |
|---|---|---|
| `standard()` | Converts columns like `MonthlyCharges` → `monthly_charges` via a regex snake_case pass | One naming convention everywhere downstream (SQL columns, API fields, React state) |
| `total_cha()` | Blank strings → `NaN` → `pd.to_numeric()`, logs how many rows were affected | TotalCharges must be a float before any arithmetic or model can touch it |
| `normal()` | Maps Yes→1 / No→0 on partner, dependents, phone_service, paperless_billing, churn | Binary encoding needed for both SQL rule filters and ML |
| `null_handler()` | Fills the now-`NaN` total_charges with that row's monthly_charges | Justified: those are exactly the tenure=0 customers with no bill yet |
| `clean()` | Runs the four steps above in order and returns the DataFrame | Single entry point — this is the only method anything else calls |

```python
# customer_cleaner.py
class CustomerCleaner:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()          # never mutate the caller's frame

    def clean(self):
        self.standard()
        self.total_cha()
        self.normal()
        self.null_handler()
        return self.df
```

### The pipeline script — two versions, one canonical

There are two pipeline files. `customer_pipeline.py` is the one to treat as canonical: it resolves paths relative to `Path(__file__)`, so it runs correctly no matter where the repo is checked out, and it writes a proper rotating log (`customer_pipeline.log`). `customer_pipeline2.py` is an earlier draft that still points at a hardcoded `D:\projectpart1\...` path from a previous machine/folder — it's a leftover, not a second live pipeline (see [Known Gaps](#known-gaps)).

Either way the flow is the same: `load_data() → CustomerCleaner().clean() → build_features() → save_outputs()`, wrapped in `try/except` so a failure is logged and re-raised rather than silently swallowed, with two hard assertions before saving (no nulls in `monthly_charges`, churn is only 0/1). The `outputs/` folder holds the timestamped proof this was actually run — seven pairs of `cleaned_customer_data_*.csv` / `customer_features_*.csv` from August 2026.

> **Connects to →** Phase 2 (the cleaned schema becomes the staging→curated load), Phase 5 (this exact class is reused inside the automated DE pipeline), Phase 6 (the six engineered features below are what ML trains on).

---

## Phase 2 — Database Layer ✅

**Goal:** Move off the flat CSV into a schema with a staging zone, a trusted curated layer, and a serving view — using MySQL and SQLAlchemy.

**Files:** `tables3.py` · `sql_alc2.py` · `dataengineer/de3.ipynb` · MySQL schema `proj`

The database follows the classic staging → curated split. **Staging** (`stg_customer_raw`) mirrors the CSV exactly — every column, including `TotalCharges`, is loaded as `VARCHAR`, deliberately untouched. **Curated** tables are typed and normalized: a `customers`/`stg_telco_customer` table, dimension tables `dim_contract` and `dim_payment`, and a fact table `fact_customer_account` joining them by surrogate key.

| Table | Defined in | Role |
|---|---|---|
| `stg_customer_raw` | `tables3.py` (`CustomerRaw`) + `sql_alc2.py` | Landing zone — exact CSV shape, all strings |
| `stg_telco_customer` | `tables3.py` (`Customer` ORM model) | Typed, cleaned customer table loaded by `sql_alc2.py:load_telco_data()` |
| `ingestion_log` | `tables3.py` (`IngestionLog`) | Audit row per load: source file, row count, status |
| `dim_contract` / `dim_payment` | `dataengineer/de3.ipynb` (pandas `to_sql`) | Lookup dimensions, one row per distinct value |
| `fact_customer_account` | `dataengineer/de3.ipynb` | tenure, charges, churn — joined to the dims by key |
| `v_high_risk_customers` | created directly in MySQL (read by `churn_service.py`) | SQL view: month-to-month + tenure<12 + above-average charges |

```python
# sql_alc2.py
# staging: load everything as text, no interpretation
df.to_sql(name="stg_customer_raw", con=engine, if_exists="replace",
          dtype={col: VARCHAR(255) for col in df.columns})

# curated: coerce types, fill the tenure=0 blanks, then insert row by row
df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
df.loc[df["TotalCharges"].isna() & (df["tenure"]==0), "TotalCharges"] = df["MonthlyCharges"]
```

**SQLAlchemy ORM** is used two ways: `tables3.py` declares `Base`/`Column` model classes for `Customer`, `CustomerRaw` and `IngestionLog` (the SQL3 lab requirement), and every read in the API layer goes through a `SessionLocal()` session rather than a raw connection.

> **Worth knowing for your demo:** The dim/fact tables and the `v_high_risk_customers` view aren't defined by a checked-in `.sql` file or an ORM class — they were materialized by running the pandas `to_sql()` calls inside `dataengineer/de3.ipynb` against the live MySQL database. The schema exists in the database, not (yet) as version-controlled DDL. Fine for a working system; worth a one-line caveat if someone asks "where's the schema file."

> **Connects to →** Phase 3 (every API query hits these exact tables/view), Phase 6 (the ML feature table sits alongside `fact_customer_account`).

---

## Phase 3 — FastAPI Backend ✅

**Goal:** One service exposing every capability — lookup, aggregate, rule-based risk, live prediction — as a REST endpoint anything can call.

**Files:** `main2.py` · `churn_service.py` · `tables3.py` (Pydantic models)

| Endpoint | Method | Purpose |
|---|---|---|
| `/customers/{id}` | GET | Single customer profile, 404 if unknown |
| `/customers` | GET | Full customer list |
| `/customers` | POST 🔒 | Create — requires `X-API-Key` |
| `/customers/{id}` | PATCH 🔒 | Partial update — requires `X-API-Key` |
| `/customers/{id}` | DELETE 🔒 | Delete — requires `X-API-Key` |
| `/customers/high-risk` | GET | Reads `v_high_risk_customers`, filterable by `limit`/`min_tenure`/`max_tenure` |
| `/churn/summary` | GET | Executive KPIs: totals, churn rate, breakdown by contract & internet service |
| `/predict-churn` | POST | Live risk score from the trained model (API5 + ML4 combined — the stub was already replaced) |

Two design choices worth understanding:

1. **Business logic never lives in a route.** `get_churn_summary()` and `get_high_risk_customers()` live in `churn_service.py` as plain functions that take a `Session` and return a dict; `main2.py` just calls them. This is exactly the "callable, not just reachable through HTTP" shape Phase 7/8 needs later to turn these into Claude tools without duplicating logic.

2. **`get_churn_summary()` is written defensively** — each query is wrapped in its own `try/except` with a fallback: it first tries the curated `fact_customer_account` + `dim_contract` join, and if that fails it falls back to computing the same aggregate straight from `stg_customer_raw` with string comparisons. That means the summary endpoint keeps working even if the curated tables haven't been (re)built yet.

```python
# main2.py
def check_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

# reads are open; writes require the header
@app.post("/customers", response_model=CustomerResponse, status_code=201)
def create_customer(customer: CustomerCreate, db: Session = Depends(get_db),
                    _: str = Depends(check_api_key)):
    ...
```

Validation is handled by Pydantic `field_validator`s on `ChurnPredictionRequest` (tenure 0–100, monthly_charges > 0) — an out-of-range value returns a `422` automatically, no manual check needed in the route.

> **Connects to →** Phase 4 (every dashboard page calls one of these endpoints), Phase 8 (these same functions become Claude's tools — no new business logic needed, only a schema wrapper).

---

## Phase 4 — React Dashboard ✅

**Goal:** A thin UI that proves the API is real — four tabs, no routing library, one shared fetch pattern.

**Files:** `CustomerDashboard/src/App.jsx` · `src/api.js` · `src/pages/ChurnSummary.jsx` · `src/pages/CustomerSearch/CustomerSearch.jsx` · `src/pages/HighRiskCustomers.jsx` · `src/pages/ChurnPrediction.jsx`

Built with **Vite + React 19**. Navigation is deliberately simple — `App.jsx` holds one `activeTab` state variable and conditionally renders one of four page components; there's no React Router, which matches the guide's note that "React scope is intentionally limited."

| Page | Calls | What it shows |
|---|---|---|
| ChurnSummary | GET /churn/summary | KPI cards + a churn-rate bar per contract type, fetched once on mount |
| CustomerSearch | GET /customers/{id} | Profile card, red/green background by churn status, graceful "not found" |
| HighRiskCustomers | GET /customers/high-risk | Sortable table, "Load More" paging, currency-formatted charges |
| ChurnPrediction | POST /predict-churn | A 4-field form → colour-coded risk bar (green/amber/red) |

```jsx
// src/pages/ChurnPrediction.jsx
const getRiskClass = () => {
  if (prediction.risk_score < 0.3) return "low-risk";
  if (prediction.risk_score <= 0.6) return "medium-risk";
  return "high-risk";
};
// width: `${risk_score * 100}%` drives the coloured bar directly off the model's own number
```

`src/api.js` reads the backend URL from `VITE_API_URL` with a `localhost:8000` fallback, and attaches the same `X-API-Key` header main2.py expects — good for a training project, but see the note on this key under [Known Gaps](#known-gaps).

> **Connects to →** Phase 8 (the planned assistant page is a fifth tab added to this exact app, reusing the same fetch/loading/error pattern).

---

## Phase 5 — Data Engineering ⚠️

**Status:** Built, not orchestrated

**Goal:** Turn the one-off Phase 1 pipeline into repeatable, quality-gated stages — and prove the same aggregations hold at a different engine (PySpark), not just a different scale.

**Files:** `dataengineer/de2.ipynb … de7.ipynb` · `dataengineer/ingestion.py` *(empty)* · `dataengineer/quality_report.json` · `dataengineer/spark_output/summary_con`

| Stage | Notebook | What it proves |
|---|---|---|
| DE1–2 Ingestion | de2.ipynb | Schema validation against the 21 expected columns before loading to staging |
| DE3 Cleaning | de3.ipynb | Reuses `CustomerCleaner`, then builds `dim_contract`/`dim_payment`/`fact_customer_account` |
| DE4 Features | de4.ipynb | Automates the same 6 engineered features from Phase 1, into `customer_ml_features` |
| DE5 PySpark | de5.ipynb | Same groupby churn-rate aggregations, run through Spark instead of pandas, written to Parquet |
| DE6 Incremental | de6.ipynb | Upsert logic so re-running the pipeline doesn't duplicate customers |
| DE7 Quality gate | de7.ipynb | Programmatic PASS/FAIL checks, written out as JSON |

```json
// dataengineer/quality_report.json
{ "check_name": "value_range_tenure", "status": "PASS",
  "value_found": { "min": "0", "max": "72" }, "threshold": { "min": 0, "max": 100 } }
// every check in this run came back PASS — real evidence the gate has been exercised
```

The PySpark step (DE5) reads the CSV with a **manually declared schema** — never `inferSchema`, which would misread `TotalCharges` — cleans blanks with `F.regexp_replace()`, encodes churn with `F.when().otherwise()`, and cross-checks that Spark's churn rate per contract type matches the pandas number from Phase 1 exactly. That cross-check is the actual point of the lab: same numbers, different engine.

> ⚠️ **Partial — orchestration missing.** DE1–DE7 exist as working, individually-runnable notebooks and scripts. **DE8 (the Airflow DAG that chains them into one scheduled daily run) doesn't exist** — no `dags/` folder anywhere in the repo. `dataengineer/ingestion.py`, which should hold the DE2 `detect → validate → load → log` functions as an importable module, is currently an empty file. Today the pipeline is run by hand, notebook by notebook.

> **Connects to →** Phase 6 (`customer_ml_features` is the ML training input), Phase 8 (AI4's daily-brief script is meant to be the 7th DAG task — there's no DAG yet to attach it to).

---

## Phase 6 — Machine Learning ⚠️

**Status:** Built, with a known defect

**Goal:** Define the problem correctly, train two comparable models, explain the winner in business terms, then wire it live and run it in batch.

**Files:** `ml/ml1.ipynb` · `ml/predict.py` · `ml/batch_score.py` · `ml/models/*.pkl` · `ml/customer_risk_table.csv`

The ML problem is defined the standard way: drop `customer_id` (identifier, not signal), one-hot encode `contract_type` and `internet_service`, and — because churn is ~73/27 — evaluate on **F1 for the churned class**, not raw accuracy (a model that predicts "No" for everyone would score 73% accuracy and be useless). Two models were trained and saved: `logistic_churn.pkl` and `tree_churn.pkl`, plus `feature_columns.pkl` recording the exact training column order.

### Live prediction — `ml/predict.py`

`predict.py` loads the logistic model once at import time, then builds a one-row DataFrame for inference:

```python
# ml/predict.py
feature_columns = list(model.feature_names_in_)

def preprocess_input(tenure, monthly_charges, contract_type, service_count):
    row = {col: 0 for col in feature_columns}   # <- everything starts at 0
    row["tenure"] = tenure
    row["monthly_charges"] = monthly_charges
    row["service_count"] = service_count
    row[f"contract_type_{contract_type}"] = 1
    return pd.DataFrame([row])[feature_columns]
```

> ⚠️ **This is the intentional bug — leave it alone until Phase 7.** Only 4 of the model's trained inputs are ever set from the real request: `tenure`, `monthly_charges`, `service_count`, and one `contract_type_*` dummy. Every other column the model was trained on — `total_charges`, `high_charge_flag`, `is_long_term_customer`, `has_streaming_bundle`, `auto_pay_flag`, and the `internet_service_*` dummies — silently stays at its placeholder value of **0** for every single prediction, regardless of the real customer. This is exactly the defect **Lab CL1** (see Phase 7) is built to find and fix with the Claude API — don't fix it by hand before then.

`ml/batch_score.py` (Lab ML5) applies `predict_churn()` to every row of `customer_ml_features.csv` via `df.apply()`, and writes `customer_risk_table.csv` — the table meant to feed the dashboard, the high-risk endpoint, and eventually the AI assistant.

> **Connects to →** Phase 3 (predict.py is imported directly into main2.py's `/predict-churn`), Phase 7 (this file is Lab CL1's whole subject).

---

## Known Gaps

None of these block a demo — the system runs — but they're the honest answer if someone asks "is this production-ready?"

1. **`predict.py`'s placeholder features** — covered above; intentional, and the whole point of Lab CL1 in Phase 7.

2. **Hardcoded absolute paths from a different machine** — `customer_pipeline2.py`, `ml/batch_score.py`, and `sql_alc2.py` all point at `D:\projectpart1\...`, a folder structure from before the project moved to `D:\telecom_churn\Telecom-Churn-project`. They'll fail on a fresh checkout until the paths are updated or made relative like `customer_pipeline.py` already does.

3. **Database credentials hardcoded in source** — `mysql+mysqlconnector://root:root@localhost:3306/proj` appears directly in `tables3.py` and `sql_alc2.py` rather than an environment variable. Harmless on a local training box, a real problem the moment this touches a shared or public repo.

4. **API key duplicated in frontend source** — the same literal string `"qwertyuiop"` sits in both `main2.py` and `CustomerDashboard/src/api.js`. Anyone opening browser dev tools sees it. Fine as a teaching stand-in for real auth (the guide calls this out explicitly as "a simple version of what JWT does"), not something to ship.

5. **axios used but not declared** — `ChurnPrediction.jsx` imports `axios`, but it isn't listed in `CustomerDashboard/package.json` dependencies — a clean `npm install` elsewhere may not pull it in.

6. **No Airflow DAG (DE8)** — every pipeline stage runs standalone today; nothing schedules or chains them. Say "the stages exist, orchestration is the next step" rather than implying it's automated end-to-end.

7. **dim/fact schema lives only in the database** — no checked-in DDL for `dim_contract`, `dim_payment`, `fact_customer_account`, or the `v_high_risk_customers` view — they were created by running notebook cells against MySQL directly, so rebuilding the database from a clean checkout means re-running `de3.ipynb` and re-creating the view by hand.

---

## Phase 7 — Extending the System with Claude 🔭

**Status:** Planned — from `customer-churn-newpart.docx`, nothing implemented yet

**Goal:** Use the Claude API twice: once as a one-time audit tool to find and fix the real bug above, then to give the whole Claude integration memory, reusable prompts, and security discipline before it's trusted with customer data.

### Pre-flight readiness — checked against your actual repo

| Task | Status |
|---|---|
| Task 1 — clear project layout | ✅ Already true: FastAPI, React, `models/`, SQL scripts each have their own place |
| Task 2 — training runnable from a cold terminal as `python train.py` | ⚠️ **Not yet true.** Training currently lives inside `ml/ml1.ipynb`, not a standalone script — this needs extracting before Lab CL1 can compare "train.py's feature columns" against predict.py, as the guide assumes |
| Task 3 — API logic callable as plain functions, not only via HTTP | ✅ Already true: `churn_service.py` was already built this way |
| Task 4 — `pip install anthropic`, `.env` with `ANTHROPIC_API_KEY`, smoke test | ❌ Not started: no `requirements.txt`, no `.env`, no `anthropic` import anywhere in the repo yet |

### Lab CL1 — Audit and fix the feature gap

| Step | Mechanism |
|---|---|
| Audit | `audit_defect.py` pastes `train.py` + `predict.py` into one Claude request and forces a structured findings list via `tool_choice` — not free-text prose |
| Confirm | The findings must name every hardcoded feature and explicitly say this is an *inference-time* bug, not a reason to retrain |
| Fix | By hand: `train.py` persists the real column list to `models/feature_columns.json`; `predict.py` reads that file instead of guessing |
| Prove it | Re-run predictions before/after, two separate git commits, a before/after risk-score table |

### Lab CL2 — Memory, prompt templates, and security

| Artifact | Purpose |
|---|---|
| `project_context.py` | Under 200 lines of durable facts (data quirks, ML rules, table names) prepended to every system prompt |
| `prompts/*.py` + `load_template()` | Three versioned templates (profile dataset, scaffold an endpoint, security-review code) — never inline prompt text in a script |
| Security checklist (in code) | Never let a prompt see `.env` secrets, validate every argument, forward only needed fields, cap tokens/history in one shared place |

The security-review template is deliberately kept isolated — callable only by a human, never wired into anything that runs automatically. The lab ends by deliberately trying to leak a `.env` value through a template and proving the guard blocks it.

> **Depends on →** Phase 6 (predict.py is the subject of CL1). **Feeds →** Phase 8 (project_context.py and the prompt-loading pattern are reused in every AI1–AI5 lab).

---

## Phase 8 — The Retention AI Assistant 🔭

**Status:** Planned — from `customer-churn-newpart.docx`, nothing implemented yet

**Goal:** Build outward from one Claude API call to a fully evaluated assistant embedded in the product — that can only ever say things your own API can prove.

### AI1 — Call Claude from the backend

A new `api/assistant.py` with one `Anthropic()` client built once at module level, and `POST /assistant/chat` added next to the existing endpoints in `main2.py`'s spirit. The system prompt states the business facts plainly — a telecom operator, ~7,043 customers, 26.5% baseline churn — and one hard rule: **never invent customer data**. This lab also includes picking a model with a documented reason, comparing thinking on/off, and turning on prompt caching (measuring the actual cache-read/cache-write token counts and the resulting cost per 1,000 requests).

### AI2 — Give Claude your own APIs as tools

This is the payoff for Phase 3's service-layer discipline: four tools — customer profile, churn summary, high-risk list, prediction — each defined with a JSON Schema and a "briefing to a new analyst" description, dispatched through one `execute_tool(name, args)` function that calls the *existing* `churn_service.py` functions. No business logic is duplicated inside the assistant. The request loop calls Claude, executes every tool call it asks for, sends the results back, and repeats — capped at a small iteration count with a clear error if exceeded.

```
React UI  ──────────────►  FastAPI (main2.py)
    │                              ▲
    │                              │ calls as tools
    └──────────────►  assistant.py (planned)
                                   │
                    ┌──────────────┼───────────────┬──────────────────┐
                    ▼              ▼                ▼                  ▼
          get_churn_summary()  get_high_risk_   predict_churn()  customer lookup
                               customers()

          — the same four functions the React dashboard already calls —
```

### AI3 — Ship it in the React UI, with guardrails

A fifth dashboard tab: a message list, an input box, and — critically — a visible line under every answer showing which tools produced it, so a support agent can trace any number back to a real query. The system prompt gets hard guardrails: never state a number that didn't come from a tool, cap any list at a small size, never speculate about causes a tool result doesn't support. Tested against deliberately tricky asks like "list every customer" or "why did they churn" (a causal claim no tool can support).

### AI4 — Headless Claude: pipeline & CI

Two scripts with no chat UI at all: a **daily brief** that compares today's vs. yesterday's risk scores by segment (sending only aggregated deltas to Claude, never raw customer rows) and forces a fixed headline/movements/actions structure — meant to slot in as the DE8 DAG's next task once that DAG exists. And a **code-review script** reading a diff from stdin, forcing structured findings via `tool_choice`, exiting non-zero on a real defect — wired into a git `pre-push` hook so it runs automatically before code reaches the shared repo.

### AI5 — Evaluate, cost, and harden

15 hand-written evaluation questions in three groups of five — single-tool, multi-tool, and genuinely unanswerable — scored on three separate rates: factual accuracy, correct tool selection, and correct refusal on the unanswerable group. Run across two models to justify a production choice on quality-vs-cost, then hardened with response/history length limits, a tool-loop iteration cap, retry-with-backoff, schema-validated tool arguments, a full audit log, and a written limitations section — what the assistant genuinely cannot know, and what it should never be used for.

> **Depends on →** Phase 3 (the tools are literally the existing endpoints), Phase 5 (AI4's daily brief wants the DE8 DAG that doesn't exist yet), Phase 7 (reuses project_context.py and the prompt-template pattern throughout).

---

## How It All Connects

One sentence per phase, in the order data actually moves:

| # | Phase | In one line |
|---|---|---|
| 1 | Python Core | Raw CSV → a trustworthy DataFrame |
| 2 | Database | DataFrame → staging → typed, joined MySQL tables + a rule-based risk view |
| 3 | FastAPI | Every capability becomes one callable, importable, testable endpoint |
| 4 | React | A human can see and act on the API without writing a query |
| 5 | Data Engineering | The one-off pipeline becomes repeatable stages with a quality gate (orchestration still manual) |
| 6 | Machine Learning | Rules become a trained, explainable, batch-scored model |
| 7 | Claude Hardening 🔭 | Claude finds and fixes a real bug, then earns memory, prompts, and guardrails |
| 8 | AI Assistant 🔭 | Claude becomes a conversational layer that can only ever say what the API already proves |

**The single idea worth carrying into any conversation about this system:** Phase 8 doesn't bolt AI onto the side of the product — it sits directly on top of Phase 3's service layer. Because `churn_service.py` was already written as plain, importable functions rather than logic buried inside HTTP routes, turning "the API" into "tools an assistant can call" is a schema-wrapping exercise, not a rewrite. That discipline, paid for back in Phase 3, is what makes Phase 8 cheap.
