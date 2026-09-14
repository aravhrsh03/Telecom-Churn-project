# Lab AI5 — Evaluation, Cost, and Hardening

## Evaluation set

`eval/questions.json` — 15 questions: 5 single-tool, 5 multi-tool, 5
genuinely unanswerable (see that file for the full list and which tool(s)
each one is expected to call).

## Running it

```
python eval/run_eval.py                    # ANTHROPIC_MODEL_DEFAULT only, cheap sanity check
python eval/run_eval.py --compare-models   # both models, for the production-choice decision below
```

Writes `eval/eval_results.json` (full transcripts + per-question scoring)
and prints the three summary rates.

## The three rates (methodology)

- **`correct_tool_selection_rate`** — did the assistant call at least the
  expected tool(s) for the question? Fully automated, unambiguous.
- **`factual_accuracy_rate`** — a **numeric-grounding proxy**: every number
  that appears in the reply must trace back (within rounding/percent
  conversion) to a number that actually came out of a tool call. This is
  not full semantic grading (see `docs/LIMITATIONS.md`) but it directly
  targets the failure mode this whole project cares about: hallucinated
  statistics.
- **`correct_refusal_rate`** — for the 5 unanswerable questions, did the
  reply contain refusal language (or, for the fake-customer-ID case,
  correctly report "not found") rather than inventing an answer?

## Results

*(Fill in after running `python eval/run_eval.py --compare-models` with a
real `ANTHROPIC_API_KEY` configured.)*

| Model | Factual accuracy | Correct tool selection | Correct refusal | Total input tokens | Total output tokens |
|---|---|---|---|---|---|
| `claude-haiku-4-5-20251001` | | | | | |
| `claude-sonnet-5` | | | | | |

**Production model choice**: *(fill in with the justification once the
table above is real — the expectation, per `docs/ai1_model_comparison.md`,
is Sonnet 5 for the interactive assistant given its tool-use reasoning
needs, unless the evaluation shows Haiku holds up on quality for
meaningfully less cost.)*

## Cost per conversation and monthly projection

```
cost_per_conversation = (avg_input_tokens * input_price + avg_output_tokens * output_price) * avg_turns_per_conversation
monthly_cost = cost_per_conversation * conversations_per_day * 30
```

*(Fill in `avg_input_tokens`/`avg_output_tokens` from `eval_results.json`'s
usage totals divided by 15, and a realistic `conversations_per_day` for a
support team of the size this system targets.)*

## Hardening implemented in code

| Requirement | Where |
|---|---|
| Max response length | `config.ASSISTANT_MAX_RESPONSE_TOKENS`, passed as `max_tokens` in `api/assistant.py` |
| Max conversation history length | `config.ASSISTANT_MAX_HISTORY_TURNS`, enforced by `security.cap_history()` |
| Tool-loop iteration cap | `config.ASSISTANT_MAX_TOOL_ITERATIONS`, enforced in `api/assistant.py`'s loop, raises `ToolLoopExceeded` (→ HTTP 422) rather than looping forever |
| Retry with backoff (rate-limit/overload) | `api/assistant.py:_retry_with_backoff()` -- exponential backoff on `RateLimitError` and 429/529 `APIStatusError` |
| Tool argument validation | `security.validate_tool_args()` (jsonschema against each tool's own schema), called first thing inside `api/tools.py:execute_tool()` |
| Audit log | `audit_log.py` -- every completed (and tool-loop-exceeded) conversation turn appended to `audit_log.jsonl`: timestamp, question, tools + args called, token usage |
| Secret-leakage guard | `security.assert_no_secrets()`, called on every outbound prompt in `api/assistant.py`, `audit_defect.py`, `scripts/security_review.py`, `pipeline/daily_brief.py`, `ci/review_diff.py` |

See `docs/LIMITATIONS.md` for what this system should never be used for.
