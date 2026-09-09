"""The only place a model id lives.

Verify ids at record time. See docs/CURRENCY.md.
Never put a model name in a lecture title.
A missing key is not an error. Pytest stays green.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Local default. Free. No key. Verify the tag at record time.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")

# Cloud ids stay empty until a live lab. Verify at record time. Do not guess.
OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "")
ANTHROPIC_CHAT_MODEL = os.environ.get("ANTHROPIC_CHAT_MODEL", "")


def has_live_key() -> bool:
    """True only when a cloud key is present. Local Ollama does not count as a key."""
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return bool(openai_key or anthropic_key)
