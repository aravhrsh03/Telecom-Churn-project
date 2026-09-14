"""
Phase 8, Lab AI5 -- run the 15-question evaluation set, score three rates,
and compare cost/quality across two models.

Scoring is intentionally automated and honest about its own limits (see
docs/ai5_evaluation_report.md): "factual accuracy" here means every number
in the reply is traceable to a real tool result (a numeric-grounding proxy,
not full semantic grading, which would need a human or a second model as
judge). "Correct tool selection" and "correct refusal" are both directly
checkable from the transcript.

Usage:
    python eval/run_eval.py                       # ANTHROPIC_MODEL_DEFAULT only
    python eval/run_eval.py --compare-models       # both models, cost/quality table
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.assistant import chat  # noqa: E402
from config import ANTHROPIC_MODEL_DEFAULT, ANTHROPIC_MODEL_STRONG  # noqa: E402

QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.json"
RESULTS_PATH = Path(__file__).resolve().parent / "eval_results.json"

NUMBER_RE = re.compile(r"-?\d+\.?\d*")


def _numbers_in(text: str) -> List[float]:
    return [float(n) for n in NUMBER_RE.findall(text) if n not in ("", "-", ".")]


def _flatten_tool_numbers(tool_calls: List[Dict[str, Any]]) -> List[float]:
    numbers = []
    for call in tool_calls:
        numbers.extend(_numbers_in(json.dumps(call["result"], default=str)))
    return numbers


def _is_grounded(reply: str, tool_calls: List[Dict[str, Any]]) -> bool:
    reply_numbers = _numbers_in(reply)
    if not reply_numbers:
        return True  # no numeric claims made -- nothing to ground
    tool_numbers = set(round(n, 2) for n in _flatten_tool_numbers(tool_calls))
    # Percent conversions (0.427 vs "42.7%") are a common, legitimate
    # transformation -- allow both the raw and *100 form to count as grounded.
    tool_numbers |= {round(n * 100, 2) for n in tool_numbers}
    return all(any(abs(round(rn, 2) - tn) < 0.5 for tn in tool_numbers) for rn in reply_numbers)


def _looks_like_refusal(reply: str) -> bool:
    markers = ["don't have", "do not have", "no way to", "can't answer", "cannot answer",
               "not available", "doesn't track", "does not track", "no tool", "not found",
               "couldn't find", "could not find", "no data"]
    lowered = reply.lower()
    return any(m in lowered for m in markers)


def run_one(question: Dict[str, Any], model: str) -> Dict[str, Any]:
    result = chat(question["question"], history=[], model=model)
    tools_called = sorted({t["tool"] for t in result["tool_calls"]})

    if question["group"] == "unanswerable":
        correct_refusal = _looks_like_refusal(result["reply"])
        correct_tool_selection = set(tools_called) == set(question["expected_tools"])
        grounded = _is_grounded(result["reply"], result["tool_calls"])
    else:
        correct_refusal = None
        correct_tool_selection = set(question["expected_tools"]).issubset(set(tools_called))
        grounded = _is_grounded(result["reply"], result["tool_calls"])

    return {
        "id": question["id"],
        "group": question["group"],
        "question": question["question"],
        "model": model,
        "reply": result["reply"],
        "tools_called": tools_called,
        "usage": result["usage"],
        "correct_tool_selection": correct_tool_selection,
        "grounded_numbers": grounded,
        "correct_refusal": correct_refusal,
    }


def run_all(model: str) -> List[Dict[str, Any]]:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    results = []
    for q in questions:
        print(f"[{model}] Q{q['id']} ({q['group']}): {q['question'][:70]}...")
        try:
            results.append(run_one(q, model))
        except Exception as e:  # noqa: BLE001
            results.append({"id": q["id"], "group": q["group"], "question": q["question"],
                             "model": model, "error": str(e)})
        time.sleep(0.5)  # gentle on rate limits
    return results


def score(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    answerable = [r for r in results if r["group"] != "unanswerable" and "error" not in r]
    unanswerable = [r for r in results if r["group"] == "unanswerable" and "error" not in r]

    factual_accuracy = sum(r["grounded_numbers"] for r in answerable) / len(answerable) if answerable else None
    tool_selection = (
        sum(r["correct_tool_selection"] for r in results if "error" not in r) / len([r for r in results if "error" not in r])
        if results else None
    )
    refusal_rate = sum(r["correct_refusal"] for r in unanswerable) / len(unanswerable) if unanswerable else None

    total_input = sum(r["usage"]["input_tokens"] for r in results if "error" not in r)
    total_output = sum(r["usage"]["output_tokens"] for r in results if "error" not in r)

    return {
        "factual_accuracy_rate": factual_accuracy,
        "correct_tool_selection_rate": tool_selection,
        "correct_refusal_rate": refusal_rate,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "n_questions": len(results),
        "n_errors": sum(1 for r in results if "error" in r),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-models", action="store_true")
    args = parser.parse_args()

    models = [ANTHROPIC_MODEL_DEFAULT, ANTHROPIC_MODEL_STRONG] if args.compare_models else [ANTHROPIC_MODEL_DEFAULT]

    all_results = {}
    for model in models:
        results = run_all(model)
        all_results[model] = {"results": results, "scores": score(results)}
        print(f"\n=== {model} ===")
        print(json.dumps(all_results[model]["scores"], indent=2))

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
