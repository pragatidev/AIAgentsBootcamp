"""S14: retrieve the wiki as a tool. Empty hit refuses. No FAISS required for tests.
FAISS is the production swap named in the lecture title. Keyword overlap is the lab stand-in.
"""

from __future__ import annotations

from pathlib import Path

WIKI = Path(__file__).resolve().parents[1] / "wiki"


STOP = {
    "the",
    "and",
    "for",
    "you",
    "your",
    "can",
    "this",
    "that",
    "what",
    "with",
    "from",
    "are",
    "not",
    "after",
}


def retrieve(question: str, k: int = 2) -> dict:
    words = [w for w in question.lower().split() if len(w) > 2 and w not in STOP]
    hits: list[dict] = []
    for path in sorted(WIKI.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        blob = text.lower()
        score = sum(1 for w in words if w in blob)
        if score:
            hits.append({"path": path.name, "score": score, "text": text.strip()})
    hits.sort(key=lambda h: (-h["score"], h["path"]))
    if not hits:
        return {"found": False, "refuse": True, "reason": "empty retrieve"}
    return {"found": True, "refuse": False, "hits": hits[:k]}
