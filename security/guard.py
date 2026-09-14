"""
Phase 7, Lab CL2 -- the security checklist, in code:

  1. Never let a prompt contain secrets from .env      -> assert_no_secrets()
  2. Validate every argument before it's used            -> validate_tool_args()
  3. Forward only the specific fields a task needs        -> (caller discipline;
     see api/tools.py's execute_tool(), which whitelists args per tool)
  4. Cap token usage and history length in one shared place -> cap_history(),
     config.ASSISTANT_MAX_* constants

All four live in code (not just as a checklist someone has to remember to
follow) precisely so the assistant/daily-brief/CI scripts in Phase 8 all
get them for free by importing this module.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import jsonschema

import config


class SecretLeakError(ValueError):
    """Raised when text about to be sent to Claude contains a real secret value."""


class ToolArgumentError(ValueError):
    """Raised when a tool call's arguments fail schema validation."""


def _secret_values() -> List[str]:
    """The actual secret values currently loaded from .env -- never their
    names, never anything hardcoded, so this stays correct as secrets
    change without needing code changes."""
    candidates = [
        config.ANTHROPIC_API_KEY,
        config.API_KEY,
        os.getenv("DB_PASSWORD"),
    ]
    # Ignore short/default-looking values that would cause false positives
    # on completely ordinary text (e.g. an empty string, or "root").
    return [v for v in candidates if v and len(v) >= 6]


def assert_no_secrets(text: str) -> None:
    """Raise SecretLeakError if any real secret value appears verbatim in
    text that's about to be sent to the Claude API (a prompt, a tool
    result, anything). Call this on EVERY outbound prompt."""
    for secret in _secret_values():
        if secret in text:
            raise SecretLeakError(
                "Refusing to send a prompt that contains a secret value "
                "(matched against ANTHROPIC_API_KEY / API_KEY / DB_PASSWORD)."
            )


def validate_tool_args(schema: Dict[str, Any], args: Dict[str, Any], tool_name: str) -> None:
    """Validate a tool call's arguments against its own JSON Schema before
    they're used for anything -- never trust the model's tool_use.input
    directly. Raises ToolArgumentError with a message safe to show back to
    the model so it can retry with corrected arguments."""
    try:
        jsonschema.validate(instance=args, schema=schema)
    except jsonschema.ValidationError as e:
        raise ToolArgumentError(f"Invalid arguments for tool '{tool_name}': {e.message}") from e


def cap_history(
    history: List[Dict[str, Any]],
    max_turns: int = config.ASSISTANT_MAX_HISTORY_TURNS,
) -> List[Dict[str, Any]]:
    """Keep only the last `max_turns` turns of conversation history, so cost
    and context stay predictable regardless of how long a conversation runs."""
    if max_turns <= 0:
        return []
    return history[-max_turns:]
