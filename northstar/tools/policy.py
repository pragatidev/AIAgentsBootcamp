"""Read the wiki. No model."""

from __future__ import annotations

from pathlib import Path

WIKI = Path(__file__).resolve().parents[1] / "wiki"


def read_policy(ticket: str) -> dict:
    path = WIKI / "return_policy.md"
    text = path.read_text(encoding="utf-8")
    return {"path": str(path.as_posix()), "text": text, "days": 30}
