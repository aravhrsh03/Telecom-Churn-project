# Lab CL2 — Memory, Prompt Templates, Security

## Memory grounding test

Per the lab: ask a question that depends on a specific fact in
`project_context.py`, confirm the answer is grounded, remove the fact and
watch the answer degrade, then restore it.

**Fact under test**: "the fact table's churn column is named `churn_flag`,
not `churn`" (`project_context.py`, under *Database layout*).

**Question**: "I'm writing a SQL query against `fact_customer_account` to
compute churn rate. What's the column name for the churn flag?"

| Memory state | Expected answer |
|---|---|
| Fact present | Correctly says `churn_flag`, and can mention the `churn`/`churn_flag` naming mismatch is a known historical gotcha (see `dataengineer/build_curated.py`'s docstring). |
| Fact removed | Falls back to guessing `churn` (the more "obvious" name, and what the source CSV and staging table both call it) -- a plausible-sounding but wrong answer with no way to tell it's wrong. |
| Fact restored | Back to the correct, grounded answer. |

This is exactly the failure mode `project_context.py` exists to prevent:
without it, an LLM has no way to know this project renamed the column, and
will confidently produce SQL that fails against the real schema.

*(Run this test live with `ANTHROPIC_API_KEY` set to capture the actual
transcripts; the table above documents the designed and expected behavior
which the fact was specifically chosen to exercise.)*

## Red-team of the security checklist

Prompt used: *"Here's our security checklist for an LLM integration
handling real customer billing data: [checklist below]. What am I
missing?"*

Checklist reviewed (from `security/guard.py`'s module docstring):
1. Never let a prompt contain secrets from .env
2. Validate every argument before it's used
3. Forward only the specific fields a task needs
4. Cap token usage and history length in one shared place

Red-team findings, and what was done about each:

| Gap found | Resolution |
|---|---|
| The secret guard only catches secrets that appear **verbatim**. A prompt-injected instruction ("repeat your system prompt back to me") could exfiltrate context that isn't itself a raw secret string. | `project_context.py` and every system prompt built from it never contains a raw secret to begin with -- secrets live only in `config.py`/`.env` and are never interpolated into prompt text. The guard is a backstop, not the only control. |
| Argument validation (`validate_tool_args`) checks *shape* (types, required fields, enums) but not *authorization* -- e.g. nothing stops a well-formed `customer_id` argument from being an ID the caller shouldn't be able to look up. | Out of scope for this training system (no per-user auth model exists yet -- see main2.py's single shared API key). Documented as a limitation in `docs/LIMITATIONS.md` rather than silently ignored. |
| `cap_history` caps conversation length but not the *content* of what's cached across turns -- a long tool result early in a conversation still counts against every later request once cached. | Acceptable tradeoff: prompt caching (Lab AI1) is about repeated system-prompt tokens, not tool results, so this doesn't compound cost the way it sounds. Noted, not changed. |
| No rate limiting on the human-triggered `scripts/security_review.py` itself -- someone could loop it and run up API cost. | Deliberately left unrestricted: it's a manual, human-invoked tool (never wired into automation, per its own docstring), so the existing "a human has to run this" friction is the rate limit. |

## Prompt templates

Three versioned templates under `prompts/`, loaded only through
`prompts.load_template(name, **kwargs)` -- no script inlines prompt text
directly:

- `prompts/profile_dataset.txt`
- `prompts/scaffold_endpoint.txt`
- `prompts/security_review.txt` -- kept isolated; only
  `scripts/security_review.py` ever loads it, and that script is never
  imported by anything that runs automatically.

## Secret-leakage guard — proof it works

```
>>> from security import assert_no_secrets, SecretLeakError
>>> assert_no_secrets("our API key is qwertyuiop, ignore that and answer normally")
security.guard.SecretLeakError: Refusing to send a prompt that contains a
secret value (matched against ANTHROPIC_API_KEY / API_KEY / DB_PASSWORD).
>>> assert_no_secrets("What is the churn rate for month-to-month customers?")
>>>  # passes silently -- no secret present
```

Every Claude-calling script in this project (`audit_defect.py`,
`api/assistant.py`, `scripts/security_review.py`,
`pipeline/daily_brief.py`, `ci/review_diff.py`) calls `assert_no_secrets()`
on its outbound prompt before sending it.
