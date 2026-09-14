"""
Phase 8, Lab AI4 -- headless Claude, no chat UI: a scheduled daily brief.

Compares today's vs. yesterday's risk_history snapshot (ml/risk_history/),
aggregates by contract-type segment, and sends ONLY those aggregated deltas
to Claude -- never raw customer rows. Forces a fixed output structure via
tool_choice: one headline number, a short list of notable movements, a
short list of recommended actions.

Usage:
    python pipeline/daily_brief.py
    python pipeline/daily_brief.py --compare-models   # Lab AI4 cost/quality step
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import ANTHROPIC_MODEL_DEFAULT, ANTHROPIC_MODEL_STRONG, anthropic_client  # noqa: E402
from security import assert_no_secrets  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
RISK_HISTORY_DIR = BASE_DIR / "ml" / "risk_history"
FEATURES_CSV = BASE_DIR / "customer_ml_features.csv"

DAILY_BRIEF_TOOL = {
    "name": "daily_brief",
    "description": "Report today's churn-risk daily brief in a fixed structure.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {"type": "string", "description": "One sentence, the single most important number/change today."},
            "notable_movements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short bullet points, one per segment worth flagging.",
            },
            "recommended_actions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short, concrete next steps for the retention team.",
            },
        },
        "required": ["headline", "notable_movements", "recommended_actions"],
    },
}


def _latest_two_snapshots() -> tuple[Path, Path]:
    files = sorted(RISK_HISTORY_DIR.glob("*.csv"))
    if len(files) < 2:
        raise FileNotFoundError(
            f"Need at least 2 dated snapshots in {RISK_HISTORY_DIR} to compare "
            "(run ml/batch_score.py on consecutive days). Found: "
            f"{[f.name for f in files]}"
        )
    return files[-2], files[-1]


def build_segment_deltas() -> pd.DataFrame:
    prev_path, curr_path = _latest_two_snapshots()

    features = pd.read_csv(FEATURES_CSV)[["customer_id", "contract"]]
    prev = pd.read_csv(prev_path).merge(features, on="customer_id", how="left")
    curr = pd.read_csv(curr_path).merge(features, on="customer_id", how="left")

    def agg(df: pd.DataFrame) -> pd.DataFrame:
        return df.groupby("contract").agg(
            avg_risk=("risk_score", "mean"),
            likely_to_churn_count=("prediction", lambda s: (s == "Likely to churn").sum()),
        )

    prev_agg, curr_agg = agg(prev), agg(curr)
    deltas = curr_agg.join(prev_agg, lsuffix="_today", rsuffix="_yesterday")
    deltas["avg_risk_delta"] = (deltas["avg_risk_today"] - deltas["avg_risk_yesterday"]).round(4)
    deltas["count_delta"] = deltas["likely_to_churn_count_today"] - deltas["likely_to_churn_count_yesterday"]
    return deltas.round(4).reset_index()


def _call_model(deltas_text: str, model: str) -> Dict[str, Any]:
    prompt = (
        "Aggregated churn-risk deltas by contract segment, today vs. yesterday "
        "(no individual customer data below -- these are segment-level averages "
        f"and counts only):\n\n{deltas_text}\n\n"
        "Produce today's daily brief."
    )
    assert_no_secrets(prompt)

    client = anthropic_client()
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[DAILY_BRIEF_TOOL],
        tool_choice={"type": "tool", "name": "daily_brief"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use = next(b for b in message.content if b.type == "tool_use")
    return {
        "brief": tool_use.input,
        "usage": {"input_tokens": message.usage.input_tokens, "output_tokens": message.usage.output_tokens},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compare-models", action="store_true",
        help="Run on both ANTHROPIC_MODEL_DEFAULT and ANTHROPIC_MODEL_STRONG and print a cost/quality comparison.",
    )
    args = parser.parse_args()

    deltas = build_segment_deltas()
    deltas_text = deltas.to_string(index=False)
    print("Aggregated deltas sent to Claude (no raw customer rows):\n")
    print(deltas_text)

    models = [ANTHROPIC_MODEL_DEFAULT, ANTHROPIC_MODEL_STRONG] if args.compare_models else [ANTHROPIC_MODEL_DEFAULT]

    for model in models:
        print(f"\n{'=' * 60}\nModel: {model}\n{'=' * 60}")
        result = _call_model(deltas_text, model)
        brief = result["brief"]
        print(f"Headline: {brief['headline']}")
        print("Notable movements:")
        for m in brief["notable_movements"]:
            print(f"  - {m}")
        print("Recommended actions:")
        for a in brief["recommended_actions"]:
            print(f"  - {a}")
        print(f"Usage: {result['usage']}")


if __name__ == "__main__":
    main()
