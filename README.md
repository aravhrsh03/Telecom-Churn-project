# Telco Customer Churn — Retention Intelligence System

An end-to-end customer-retention platform built on the IBM/Telco Customer Churn
dataset (7,043 customers, ~26.5% churn): data cleaning, a MySQL warehouse, a
FastAPI service, a React dashboard, churn-risk models, and a Claude-powered
retention assistant.

```
CSV ─► ingestion ─► clean + curate ─► MySQL ─► FastAPI ─► React dashboard
                         │                        ▲
                         └─► features ─► ML models ┴─► Claude assistant (tool-calling)
```

## Features

- **Data pipeline** – landing CSV → staging → cleaned/curated tables with a quality gate (`dataengineer/`, `customer_cleaner.py`).
- **Database layer** – SQLAlchemy models and ingestion log (`tables3.py`, `sql_alc2.py`, `db/init_db.py`).
- **REST API** – customer CRUD, churn summary, high-risk list, engineered features, and churn prediction (`main2.py`), protected by an `X-API-Key` header.
- **ML** – Logistic Regression and Decision Tree classifiers (`train.py`, `ml/predict.py`), plus daily batch scoring with history snapshots (`ml/batch_score.py`).
- **Dashboard** – React + Vite app with churn summary, customer search, high-risk customers, prediction form and assistant chat (`CustomerDashboard/`).
- **Retention assistant** – Claude with tool calling over real data (customer profile, churn summary, high-risk list, prediction), with prompt caching, audit logging, argument validation and secret/history guards (`api/`, `security/`, `audit_log.py`).
- **Automation** – runnable pipeline (`pipeline/run_pipeline.py`), Airflow DAG (`dags/`), daily AI brief (`pipeline/daily_brief.py`), CI diff reviewer and pre-push hook (`ci/`, `.githooks/`), and a 15-question assistant eval (`eval/`).

## Project layout

| Path | Purpose |
|---|---|
| `main2.py` | FastAPI app |
| `churn_service.py` | Shared SQL queries used by the API and assistant tools |
| `config.py` | Settings loaded from `.env` |
| `tables3.py`, `sql_alc2.py`, `db/` | ORM models, raw staging load, DB bootstrap |
| `customer_cleaner.py`, `dataengineer/` | Cleaning, ingestion, curated tables, quality report |
| `train.py`, `ml/` | Model training, prediction, batch scoring, saved models |
| `api/` | Assistant loop and tool definitions |
| `security/`, `audit_log.py`, `project_context.py`, `prompts/` | Guardrails, audit log, shared context, prompt templates |
| `pipeline/`, `dags/` | Orchestration and daily brief |
| `ci/`, `scripts/`, `.githooks/`, `eval/` | Review tooling and evaluation |
| `CustomerDashboard/` | React frontend |
| `docs/`, `CHURN_SYSTEM_DEEP_DIVE.md` | Design notes, limitations, evaluation report |

## Setup

Requirements: Python 3.10+, MySQL, Node 18+.

```bash
pip install -r requirements.txt
cp .env.example .env          # set DB credentials, API_KEY, ANTHROPIC_API_KEY
```

Create the database named in `DB_NAME` (default `proj`), then load and curate the data:

```bash
python db/init_db.py
```

## Running

```bash
# API  (http://localhost:8000/docs)
uvicorn main2:app --reload

# Dashboard  (http://localhost:5173)
cd CustomerDashboard
cp .env.example .env          # VITE_API_URL, VITE_API_KEY (match API_KEY)
npm install && npm run dev

# Train models / score all customers
python train.py
python ml/batch_score.py

# Full pipeline (ingest → clean → quality gate → score → notify)
python pipeline/run_pipeline.py            # add --with-brief for the AI daily brief
```

Optional: `git config core.hooksPath .githooks` enables the pre-push AI diff review.

## API

All routes except `/` need the `X-API-Key` header.

| Method | Route | Description |
|---|---|---|
| GET | `/customers`, `/customers/{id}` | List / fetch customers |
| POST / PATCH / DELETE | `/customers`, `/customers/{id}` | Create / update / delete |
| GET | `/customers/high-risk` | Rule-based high-risk customers |
| GET | `/customers/{id}/features` | Engineered ML features |
| GET | `/churn/summary` | Churn counts and rate |
| POST | `/predict-churn` | Model churn probability |
| POST | `/assistant/chat` | Tool-calling retention assistant |

## Model results

On a stratified holdout (1,409 rows), both models reach roughly 0.79 accuracy and
0.57–0.58 F1 on the churned class (see `train.py` output and `docs/`).

## Limitations

The assistant cannot explain *why* a customer leaves, forecast the future, or use
data outside this dataset. See `docs/LIMITATIONS.md`.
