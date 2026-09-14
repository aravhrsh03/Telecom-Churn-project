# Lab AI1 — Model choice, thinking, and prompt caching

## Model comparison

| Model | Price (per M tokens, in/out) | Context window | Best fit in this system |
|---|---|---|---|
| Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | Lowest cost of the three | Large | Headless/background jobs: `pipeline/daily_brief.py`, `ci/review_diff.py` -- structured, single-shot, high-volume, cost-sensitive. Set as `ANTHROPIC_MODEL_DEFAULT`. |
| Claude Sonnet 5 (`claude-sonnet-5`) | Mid cost | Large | The interactive retention assistant (`api/assistant.py`) and `audit_defect.py` -- needs real multi-step tool-use reasoning and higher answer quality for a human in the loop. Set as `ANTHROPIC_MODEL_STRONG`. |
| Claude Opus 5 (`claude-opus-5`) | Highest cost | Large | Not used by default anywhere in this system -- reserved as a documented upgrade path if Sonnet 5's evaluation scores (see `docs/ai5_evaluation_report.md`) ever fall short on the harder multi-tool questions. |

**Decision**: `ANTHROPIC_MODEL_DEFAULT = claude-haiku-4-5-20251001` for headless,
high-volume, low-stakes jobs; `ANTHROPIC_MODEL_STRONG = claude-sonnet-5` for
anything a person is directly reading the answer to (the assistant, the
one-off audit). Both are set in `config.py` and overridable via `.env`
without touching code.

## Thinking on vs. off

Test question (requires real reasoning, not a lookup): *"Customer
3668-QPYBK has a month-to-month contract, tenure 2, and pays $53.85/month.
If I could move them to a two-year contract at the same price, roughly how
much would their churn risk drop, and is that worth a retention discount
that costs less than their current annual revenue?"*

This requires: one `predict_churn` call for their real profile, one
hypothetical `predict_churn` call for the two-year scenario, then
comparing the delta against `monthly_charges * 12` -- multi-step, and the
final judgment call ("worth it?") is exactly what extended thinking is for.

Run this once `ANTHROPIC_API_KEY` is configured:

```
python -c "
from api.assistant import chat
r = chat('<question above>', use_thinking=False)
print('thinking OFF:', r['reply'][:400], r['usage'])
r2 = chat('<question above>', use_thinking=True)
print('thinking ON :', r2['reply'][:400], r2['usage'])
"
```

Expected shape of the result (fill in with real numbers after running):

| | Answer quality | Output tokens | Notable difference |
|---|---|---|---|
| Thinking off | | | |
| Thinking on | | | |

## Prompt caching

The system prompt (`api/assistant.py:SYSTEM_PROMPT`, built from
`project_context.CONTEXT`) is marked `cache_control: {"type": "ephemeral"}`.
Calling the endpoint twice in a row should show a `cache_creation_input_tokens`
cost on the first call and a much cheaper `cache_read_input_tokens` hit on
the second:

```
curl -s -X POST http://localhost:8001/assistant/chat -H "Content-Type: application/json" \
  -d '{"message":"What is our churn rate?"}' | python -m json.tool
# run the exact same request again immediately after
curl -s -X POST http://localhost:8001/assistant/chat -H "Content-Type: application/json" \
  -d '{"message":"What is our churn rate?"}' | python -m json.tool
```

| Call | cache_creation_input_tokens | cache_read_input_tokens |
|---|---|---|
| 1st (cold) | | |
| 2nd (warm) | | |

## Cost per 1,000 requests

Once the numbers above are filled in:

```
cost_per_1000_no_cache = 1000 * (system_prompt_tokens + question_tokens) * input_price
cost_per_1000_with_cache = 1000 * (cache_read_tokens + question_tokens) * input_price
                          + one_time_cache_write_cost
```

(Fill in with real token counts and the per-model pricing table above.)
