"""
Phase 7, Lab CL1 -- the scripted (API) half of the audit.

The informal, disposable first pass ("does anything here look wrong?") was
done in chat -- see docs/cl1_first_pass_review.md. This script is the
version that needs to run the same way twice: it pastes train.py and the
PRE-FIX predict.py into one Claude request and forces a structured findings
response via tool_choice, so the output is a parseable artifact
(audit_findings.json), not prose that has to be re-read by a human each time.

Usage:
    python audit_defect.py
    python audit_defect.py --predict-file some/other/predict.py

Requires ANTHROPIC_API_KEY in .env (see .env.example).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import ANTHROPIC_MODEL_STRONG, anthropic_client

BASE_DIR = Path(__file__).resolve().parent

REPORT_FINDINGS_TOOL = {
    "name": "report_findings",
    "description": (
        "Report structured findings from auditing predict.py's inference-time "
        "feature construction against train.py's training-time feature list."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "description": "One entry per feature that is NOT correctly computed from real input at inference time.",
                "items": {
                    "type": "object",
                    "properties": {
                        "feature_name": {"type": "string"},
                        "issue": {"type": "string", "description": "What predict.py actually does wrong for this feature."},
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    },
                    "required": ["feature_name", "issue", "severity"],
                },
            },
            "is_training_problem": {
                "type": "boolean",
                "description": "Must be false unless the model itself (not the inference code) needs to change. This class of bug is inference-time only.",
            },
            "recommended_fix_summary": {
                "type": "string",
                "description": "A concrete, inference-time fix (no retraining).",
            },
            "plain_english_summary": {
                "type": "string",
                "description": "A 3-5 sentence, non-technical explanation suitable for a written note to a non-technical stakeholder.",
            },
        },
        "required": ["findings", "is_training_problem", "recommended_fix_summary", "plain_english_summary"],
    },
}

SYSTEM_PROMPT = """You are auditing a telecom churn-prediction codebase (IBM/Telco dataset,
7,043 customers, 26.5% churn baseline). You will be given train.py (how the model was
trained -- the ground truth for what features it expects) and predict.py (how a live
FastAPI endpoint builds a feature vector for one customer at inference time).

Your only job: find every feature that predict.py does NOT correctly compute from real
input data -- i.e. every place it substitutes a placeholder (commonly 0) instead of a
value derived from what the caller actually provided.

This is scoped as an inference-time bug, not a training problem: the model itself is
fine, so is_training_problem must be false and your recommended fix must never involve
retraining. Call report_findings with your results -- do not respond in free text."""


def run_audit(predict_file: Path) -> dict:
    train_py = (BASE_DIR / "train.py").read_text(encoding="utf-8")
    predict_py = predict_file.read_text(encoding="utf-8")

    client = anthropic_client()
    message = client.messages.create(
        model=ANTHROPIC_MODEL_STRONG,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[REPORT_FINDINGS_TOOL],
        tool_choice={"type": "tool", "name": "report_findings"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"train.py:\n```python\n{train_py}\n```\n\n"
                    f"predict.py:\n```python\n{predict_py}\n```"
                ),
            }
        ],
    )

    tool_use = next(b for b in message.content if b.type == "tool_use")
    result = tool_use.input
    result["_usage"] = {
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predict-file",
        type=Path,
        default=BASE_DIR / "docs" / "predict_before_fix.py",
        help="Path to the predict.py version to audit (defaults to the pre-fix snapshot).",
    )
    parser.add_argument(
        "--out", type=Path, default=BASE_DIR / "audit_findings.json",
        help="Where to write the structured findings.",
    )
    args = parser.parse_args()

    result = run_audit(args.predict_file)

    print(f"is_training_problem: {result['is_training_problem']}")
    print(f"\n{len(result['findings'])} findings:")
    for f in result["findings"]:
        print(f"  [{f['severity']}] {f['feature_name']}: {f['issue']}")
    print(f"\nRecommended fix:\n{result['recommended_fix_summary']}")
    print(f"\nPlain-English summary:\n{result['plain_english_summary']}")
    print(f"\nToken usage: {result['_usage']}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
