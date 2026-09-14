"""
DE8 -- the Airflow DAG version of pipeline/run_pipeline.py, which is the
version actually exercised in this repo (Airflow itself is a heavy
dependency -- `pip install apache-airflow` plus `airflow db init` -- and
isn't assumed to be installed just to finish Phase 7/8). This file is
correct, real Airflow code; running it for real means placing it under
your Airflow `dags/` folder and pointing $AIRFLOW_HOME at a real Airflow
installation.

Chain: ingest >> validate_quality >> clean >> build_features >> score
       >> daily_brief >> notify

Lab AI4's daily brief is task 6 here, exactly as that lab describes
("scheduled to run after your batch scoring step").
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from airflow import DAG
from airflow.operators.python import PythonOperator


def _ingest():
    from sqlalchemy import create_engine
    from config import DATABASE_URL
    from dataengineer import ingestion
    engine = create_engine(DATABASE_URL)
    results = ingestion.process_landing(engine)
    if not results or any(r["status"] == "REJECTED" for r in results):
        raise RuntimeError(f"Ingestion failed or rejected a file: {results}")


def _clean_and_build_curated():
    from sqlalchemy import create_engine
    from config import DATABASE_URL
    from dataengineer import build_curated
    engine = create_engine(DATABASE_URL)
    cleaned = build_curated.clean_staging(engine)
    build_curated.build_curated_tables(cleaned, engine)
    build_curated.create_high_risk_view(engine)


def _validate_quality():
    from sqlalchemy import create_engine
    from config import DATABASE_URL
    from dataengineer import build_curated
    engine = create_engine(DATABASE_URL)
    cleaned = build_curated.clean_staging(engine)
    build_curated.quality_report(cleaned)  # raises on failure -> blocks downstream tasks


def _build_features_and_score():
    sys.path.insert(0, str(PROJECT_ROOT / "ml"))
    import batch_score
    batch_score.main()


def _daily_brief():
    from pipeline import daily_brief
    from config import ANTHROPIC_MODEL_DEFAULT
    deltas = daily_brief.build_segment_deltas()
    result = daily_brief._call_model(deltas.to_string(index=False), ANTHROPIC_MODEL_DEFAULT)
    print("Daily brief headline:", result["brief"]["headline"])


def _notify(**context):
    print("Customer intelligence pipeline complete.")


with DAG(
    dag_id="customer_pipeline_dag",
    description="Ingest -> clean -> curate -> quality gate -> score -> daily brief -> notify",
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["churn", "phase5", "phase8"],
) as dag:

    ingest = PythonOperator(task_id="ingest", python_callable=_ingest)
    validate_quality = PythonOperator(task_id="validate_quality", python_callable=_validate_quality)
    clean = PythonOperator(task_id="clean_and_build_curated", python_callable=_clean_and_build_curated)
    build_features_and_score = PythonOperator(task_id="build_features_and_score", python_callable=_build_features_and_score)
    daily_brief_task = PythonOperator(task_id="daily_brief", python_callable=_daily_brief)
    notify = PythonOperator(task_id="notify", python_callable=_notify)

    ingest >> validate_quality >> clean >> build_features_and_score >> daily_brief_task >> notify
