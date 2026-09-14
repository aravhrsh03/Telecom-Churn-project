"""
The orchestration pipeline Lab AI4 refers to when it says "add this script
as a task in your pipeline, scheduled to run after your batch scoring
step." This is the runnable version -- see dags/customer_pipeline_dag.py
for the Airflow DAG that expresses the same chain for a scheduler (requires
`pip install apache-airflow`, a heavy dependency not assumed to be
installed here).

Chain: ingest -> clean+curate -> quality gate -> batch score -> daily brief
-> notify. Each stage is one of the functions already built and tested
individually in earlier phases -- this just calls them in order and stops
on the first failure, same as an Airflow DAG's task dependencies would.

Usage:
    python pipeline/run_pipeline.py             # skips the daily brief
                                                  # (needs 2+ days of history
                                                  # and ANTHROPIC_API_KEY)
    python pipeline/run_pipeline.py --with-brief
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pipeline")


def run(with_brief: bool = False) -> None:
    from config import DATABASE_URL
    from sqlalchemy import create_engine

    engine = create_engine(DATABASE_URL)

    logger.info("STAGE 1/6: ingest")
    from dataengineer import ingestion
    results = ingestion.process_landing(engine)
    logger.info("ingest -> %s", results)

    logger.info("STAGE 2/6: clean + build curated tables")
    from dataengineer import build_curated
    cleaned = build_curated.clean_staging(engine)
    build_curated.build_curated_tables(cleaned, engine)
    build_curated.create_high_risk_view(engine)

    logger.info("STAGE 3/6: quality gate")
    build_curated.quality_report(cleaned)  # raises AssertionError -> stops the pipeline on failure

    logger.info("STAGE 4/6: batch scoring")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ml"))
    import batch_score
    batch_score.main()

    if with_brief:
        logger.info("STAGE 5/6: daily brief")
        from pipeline import daily_brief
        deltas = daily_brief.build_segment_deltas()
        from config import ANTHROPIC_MODEL_DEFAULT
        result = daily_brief._call_model(deltas.to_string(index=False), ANTHROPIC_MODEL_DEFAULT)
        logger.info("daily brief headline: %s", result["brief"]["headline"])
    else:
        logger.info("STAGE 5/6: daily brief -- skipped (pass --with-brief; needs 2+ days of history + API key)")

    logger.info("STAGE 6/6: notify")
    logger.info("Customer intelligence pipeline complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-brief", action="store_true")
    args = parser.parse_args()
    run(with_brief=args.with_brief)
