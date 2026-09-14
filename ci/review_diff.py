"""
Phase 8, Lab AI4 -- headless Claude in CI: read a diff from stdin, force a
structured findings response, exit non-zero if it finds a real defect.

No CLI tooling beyond git itself is required -- this is meant to be piped
straight from git:

    git diff HEAD~1 | python ci/review_diff.py
    git diff --cached | python ci/review_diff.py

Wired into .githooks/pre-push (see that file) so it runs automatically
before code reaches the shared repo.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import ANTHROPIC_MODEL_STRONG, anthropic_client  # noqa: E402
from security import assert_no_secrets  # noqa: E402

REVIEW_TOOL = {
    "name": "report_review_findings",
    "description": "Report code-review findings for a git diff.",
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "issue": {"type": "string"},
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    },
                    "required": ["file", "issue", "severity"],
                },
            },
        },
        "required": ["findings"],
    },
}

SYSTEM_PROMPT = """You are reviewing a git diff for a telecom churn-prediction system before
it merges. Flag real defects only: correctness bugs, a feature silently defaulted instead of
computed, a hardcoded secret or path, a broken import, a query that can't work against the
actual schema. Do not flag style preferences or anything you are not confident is a real
problem. If the diff is clean, return an empty findings array -- do not invent an issue to
have something to say. Call report_review_findings with your results."""


def review(diff_text: str) -> list[dict]:
    assert_no_secrets(diff_text)

    client = anthropic_client()
    message = client.messages.create(
        model=ANTHROPIC_MODEL_STRONG,
        max_tokens=1536,
        system=SYSTEM_PROMPT,
        tools=[REVIEW_TOOL],
        tool_choice={"type": "tool", "name": "report_review_findings"},
        messages=[{"role": "user", "content": f"```diff\n{diff_text}\n```"}],
    )
    tool_use = next(b for b in message.content if b.type == "tool_use")
    return tool_use.input["findings"]


def main() -> None:
    diff_text = sys.stdin.read()
    if not diff_text.strip():
        print("No diff on stdin -- nothing to review.")
        sys.exit(0)

    findings = review(diff_text)

    if not findings:
        print("review_diff: clean, no findings.")
        sys.exit(0)

    print(f"review_diff: {len(findings)} finding(s):\n")
    for f in findings:
        print(f"  [{f['severity']}] {f['file']}: {f['issue']}")
    sys.exit(1)


if __name__ == "__main__":
    main()
