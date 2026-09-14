"""
DE2 -- Ingestion flow: detect a landing file, validate its schema against the
21 expected Telco columns, load it into stg_customer_raw, and log the result.

This file existed but was empty. It's filled in here because Phase 8's AI4
lab explicitly reuses "your orchestration pipeline" -- there needs to be a
real ingestion stage for the rest of the pipeline (and the daily brief) to
sit on top of.
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import sys as _sys

import pandas as pd
from sqlalchemy.engine import Engine

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tables3 import Base, IngestionLog, SessionLocal  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
LANDING_DIR = BASE_DIR / "data" / "landing"
RAW_DIR = BASE_DIR / "data" / "raw"
REJECTED_DIR = BASE_DIR / "data" / "rejected"

EXPECTED_COLS = [
    "customerID", "gender", "SeniorCitizen", "Partner", "Dependents", "tenure",
    "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity",
    "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
    "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod",
    "MonthlyCharges", "TotalCharges", "Churn",
]


def detect_files() -> List[Path]:
    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(LANDING_DIR.glob("*.csv"))


def validate_schema(filepath: Path) -> Tuple[bool, List[str]]:
    with open(filepath, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    return header == EXPECTED_COLS, header


def load_to_staging(filepath: Path, engine: Engine) -> Tuple[int, int]:
    df = pd.read_csv(filepath, dtype=str, keep_default_na=False)
    df.to_sql("stg_customer_raw", engine, if_exists="replace", index=False)
    distinct_ids = df["customerID"].nunique() if "customerID" in df.columns else 0
    return len(df), distinct_ids


def log_ingestion(engine: Engine, filename: str, status: str, rows: int,
                   distinct_ids: int = 0, reason: str = "") -> None:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        session.add(IngestionLog(
            source_file=filename,
            loaded_at=datetime.now(),
            row_count=rows,
            distinct_customer_ids=distinct_ids,
            status=status,
            reason=reason or None,
        ))
        session.commit()
    finally:
        session.close()


def process_landing(engine: Engine) -> List[dict]:
    """Detect -> validate -> load -> log for every file currently in landing/."""
    results = []
    for filepath in detect_files():
        ok, header = validate_schema(filepath)
        if not ok:
            REJECTED_DIR.mkdir(parents=True, exist_ok=True)
            reason = f"schema mismatch: expected {len(EXPECTED_COLS)} cols, got {len(header)}"
            logger.warning("REJECTED %s: %s", filepath.name, reason)
            log_ingestion(engine, filepath.name, "REJECTED", 0, reason=reason)
            results.append({"file": filepath.name, "status": "REJECTED", "reason": reason})
            continue

        rows, distinct_ids = load_to_staging(filepath, engine)
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("LOADED %s: %s rows (%s distinct customer ids)", filepath.name, rows, distinct_ids)
        log_ingestion(engine, filepath.name, "LOADED", rows, distinct_ids=distinct_ids)
        results.append({"file": filepath.name, "status": "LOADED", "rows": rows})

    return results


if __name__ == "__main__":
    from config import DATABASE_URL
    from sqlalchemy import create_engine

    eng = create_engine(DATABASE_URL)
    print(process_landing(eng))
