"""
Central configuration, loaded once from environment variables / .env.

Phase 7 Pre-Flight + Lab CL2 security checklist item: no secret should be
hardcoded in source. Every value here has a fallback that matches this
project's previous hardcoded default, so nothing breaks for anyone who
hasn't created a .env yet -- but anything sensitive (API keys) has no
working fallback and must come from .env.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Database -----------------------------------------------------------
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
# "127.0.0.1" rather than "localhost": mysql-connector-python and pymysql
# resolve "localhost" differently on Windows (named pipe vs TCP), which can
# silently point them at two different local MySQL instances.
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "proj")

# Standardized on pymysql everywhere: mysql-connector-python's SQLAlchemy 2.x
# batch-insert path (insertmanyvalues) proved unreliable loading the full
# 7,043-row dataset (PendingRollbackError partway through the batch).
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)
DATABASE_URL_PYMYSQL = DATABASE_URL  # kept as an alias -- some scripts import this name

# --- FastAPI service auth ------------------------------------------------
# Matches the previous hardcoded value so existing local setups keep working.
API_KEY = os.getenv("API_KEY", "qwertyuiop")

# --- Claude / Anthropic (Phase 7 + 8) ------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # no fallback -- must be set to use AI features
ANTHROPIC_MODEL_DEFAULT = os.getenv("ANTHROPIC_MODEL_DEFAULT", "claude-haiku-4-5-20251001")
ANTHROPIC_MODEL_STRONG = os.getenv("ANTHROPIC_MODEL_STRONG", "claude-sonnet-5")

# --- Shared assistant hardening (Lab AI5) --------------------------------
ASSISTANT_MAX_HISTORY_TURNS = int(os.getenv("ASSISTANT_MAX_HISTORY_TURNS", "8"))
ASSISTANT_MAX_TOOL_ITERATIONS = int(os.getenv("ASSISTANT_MAX_TOOL_ITERATIONS", "5"))
ASSISTANT_MAX_RESPONSE_TOKENS = int(os.getenv("ASSISTANT_MAX_RESPONSE_TOKENS", "1024"))
ASSISTANT_MAX_LIST_ITEMS = int(os.getenv("ASSISTANT_MAX_LIST_ITEMS", "20"))


def anthropic_client():
    """Build an Anthropic client, failing loudly (not silently) if no key is configured."""
    import anthropic

    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key "
            "before using any Claude-powered feature (audit_defect.py, the assistant, "
            "the daily brief, or the CI review script)."
        )
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
