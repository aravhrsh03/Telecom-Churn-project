"""
Phase 8.

Lab AI1 -- a single Claude call from the backend, with prompt caching and an
honest system prompt.

Lab AI2 -- the tool-calling request loop: call Claude, and while it asks for
tools, execute every requested call, append the assistant's turn UNCHANGED,
send all results back together, repeat (capped).
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import anthropic

import project_context
from api.tools import TOOLS, execute_tool
from config import ANTHROPIC_MODEL_STRONG, ASSISTANT_MAX_RESPONSE_TOKENS, ASSISTANT_MAX_TOOL_ITERATIONS, anthropic_client
from security import assert_no_secrets, cap_history

# Built once, at module level (Lab AI1) -- not re-created per request.
_client: Optional[anthropic.Anthropic] = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic_client()
    return _client


SYSTEM_PROMPT = f"""\
You are the retention assistant embedded in a telecom operator's internal
customer dashboard. You help support agents and the retention team answer
questions about customers and churn risk.

{project_context.CONTEXT}

Every number you state must come from a tool call in this conversation.
Never invent a customer, a churn reason, or a statistic.
"""


class ToolLoopExceeded(RuntimeError):
    """Raised when the assistant asks for more tool round-trips than allowed."""


def _retry_with_backoff(fn, max_attempts: int = 4):
    """Lab AI5 hardening: retry on rate-limit/overload errors with backoff."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
            is_overload = isinstance(e, anthropic.APIStatusError) and e.status_code in (429, 529)
            if attempt == max_attempts - 1 or not (isinstance(e, anthropic.RateLimitError) or is_overload):
                raise
            time.sleep(2 ** attempt)


def chat(
    message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    use_thinking: bool = False,
    model: str = ANTHROPIC_MODEL_STRONG,
) -> Dict[str, Any]:
    """Run one user turn through the tool-calling loop and return the reply,
    the tool-call trail (for the UI's "how was this answer produced" line),
    and usage totals across every round-trip."""
    client = get_client()
    history = cap_history(history or [])

    messages: List[Dict[str, Any]] = list(history) + [{"role": "user", "content": message}]
    assert_no_secrets(message)

    tool_trail: List[Dict[str, Any]] = []
    total_usage = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}

    system_blocks = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]

    kwargs: Dict[str, Any] = dict(
        model=model,
        max_tokens=ASSISTANT_MAX_RESPONSE_TOKENS,
        system=system_blocks,
        tools=TOOLS,
        messages=messages,
    )
    if use_thinking:
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": 4096}
        kwargs["max_tokens"] = ASSISTANT_MAX_RESPONSE_TOKENS + 4096

    for iteration in range(ASSISTANT_MAX_TOOL_ITERATIONS):
        response = _retry_with_backoff(lambda: client.messages.create(**kwargs))

        for key in total_usage:
            total_usage[key] += getattr(response.usage, key, 0) or 0

        if response.stop_reason != "tool_use":
            reply_text = "".join(b.text for b in response.content if b.type == "text")
            return {
                "reply": reply_text,
                "tool_calls": tool_trail,
                "usage": total_usage,
                "iterations": iteration + 1,
            }

        # Append the assistant's turn UNCHANGED before the tool results.
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = execute_tool(block.name, block.input)
            tool_trail.append({"tool": block.name, "args": block.input, "result": result})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": _safe_json(result),
            })

        messages.append({"role": "user", "content": tool_results})
        kwargs["messages"] = messages

    raise ToolLoopExceeded(
        f"Assistant requested more than {ASSISTANT_MAX_TOOL_ITERATIONS} tool round-trips for one message."
    )


def _safe_json(result: Dict[str, Any]) -> str:
    import json
    return json.dumps(result, default=str)
