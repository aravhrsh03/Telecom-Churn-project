"""
Phase 7, Lab CL2 -- the security-review template, isolated.

This is the ONLY place prompts/security_review.txt is ever loaded. It is
deliberately not imported by main2.py, api/assistant.py, any pipeline
script, or any git hook -- a human runs it on purpose, reads the output,
and decides what to do. Wiring a security reviewer into something that
runs unattended defeats the point of having a human review security
findings before they're acted on.

Usage:
    git diff HEAD~1 | python scripts/security_review.py
    git diff --cached | python scripts/security_review.py
"""
from __future__ import annotations

import sys

from config import ANTHROPIC_MODEL_STRONG, anthropic_client
from prompts import load_template
from security import assert_no_secrets


def review(diff_text: str) -> str:
    prompt = load_template("security_review", diff=diff_text)
    assert_no_secrets(prompt)  # the diff itself could contain a leaked secret

    client = anthropic_client()
    message = client.messages.create(
        model=ANTHROPIC_MODEL_STRONG,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def main() -> None:
    diff_text = sys.stdin.read()
    if not diff_text.strip():
        print("No diff on stdin -- try: git diff HEAD~1 | python scripts/security_review.py")
        sys.exit(1)

    print(review(diff_text))


if __name__ == "__main__":
    main()
