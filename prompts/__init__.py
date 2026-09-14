"""
Phase 7, Lab CL2 -- reusable, versioned prompt templates.

Never inline template text directly in a script. Every prompt lives here as
a plain .txt file with {placeholder} slots, loaded through load_template().
"""
from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_template(name: str, **kwargs: str) -> str:
    """Load prompts/<name>.txt and fill in {placeholder} slots.

    Raises FileNotFoundError for an unknown template name, and KeyError if a
    placeholder in the template wasn't supplied -- both deliberately loud
    rather than silently producing a half-filled prompt.
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"No prompt template named '{name}' in {PROMPTS_DIR}")
    template = path.read_text(encoding="utf-8")
    return template.format(**kwargs)
