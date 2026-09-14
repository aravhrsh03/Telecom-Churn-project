"""
Phase 8, Lab AI5 -- an audit log recording every question, the tools called
with their arguments, and token usage. Append-only JSONL so it's trivial to
tail, grep, or load into pandas later.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

LOG_PATH = Path(__file__).resolve().parent / "audit_log.jsonl"


def record(question: str, tool_calls: List[Dict[str, Any]], usage: Dict[str, Any], **extra: Any) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "tool_calls": [{"tool": t["tool"], "args": t["args"]} for t in tool_calls],
        "usage": usage,
        **extra,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
