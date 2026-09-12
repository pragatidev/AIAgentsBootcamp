"""Guides the refund-path loop loads before a tool call."""

from pathlib import Path

GUIDES_DIR = Path(__file__).resolve().parent

# PLANTED MISS: a rule with no decision in it. Lab 20.2 shows it changes nothing.
VAGUE_GUIDE = "Be careful with refunds."


def load_guide(name: str = "no_repeat_refund.md") -> str:
    path = GUIDES_DIR / name
    return path.read_text(encoding="utf-8")
