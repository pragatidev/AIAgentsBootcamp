"""Policy search over the DataFlow knowledge base. No model."""

from __future__ import annotations

import re
from pathlib import Path

from langchain.tools import tool

WIKI = Path(__file__).resolve().parents[1] / "wiki"
KNOWLEDGE_BASE = Path(__file__).resolve().parents[1] / "knowledge_base"

_STOP = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "to",
    "of",
    "and",
    "or",
    "for",
    "on",
    "in",
    "it",
    "do",
    "you",
    "your",
    "my",
    "i",
    "we",
    "what",
    "how",
    "can",
    "please",
    "me",
    "this",
    "that",
    "with",
    "from",
    "at",
    "as",
    "if",
    "not",
    "no",
    "yes",
    "just",
    "about",
    "our",
    "their",
}


def read_policy(ticket: str) -> dict:
    path = WIKI / "return_policy.md"
    text = path.read_text(encoding="utf-8")
    return {"path": str(path.as_posix()), "text": text, "days": 30}


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if w not in _STOP and len(w) > 2]


def _paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n|^\s*---\s*$", text, flags=re.MULTILINE)
    out: list[str] = []
    for chunk in chunks:
        cleaned = " ".join(chunk.strip().split())
        if cleaned:
            out.append(cleaned)
    return out


def search_policy_docs(question: str) -> dict:
    """Keyword search over markdown and txt files under knowledge_base/."""
    query = _tokens(question)
    if not query:
        return {
            "found": False,
            "reason": "no searchable terms in the question",
            "question": question,
        }
    query_set = set(query)
    best: dict | None = None
    best_score = 0
    files: list[Path] = []
    for suffix in (".md", ".markdown", ".txt"):
        files.extend(KNOWLEDGE_BASE.rglob(f"*{suffix}"))
    for path in files:
        body = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(KNOWLEDGE_BASE).as_posix()
        name_hits = len(query_set.intersection(_tokens(path.stem.replace("_", " "))))
        for paragraph in _paragraphs(body):
            para_tokens = _tokens(paragraph)
            if not para_tokens:
                continue
            overlap = query_set.intersection(para_tokens)
            score = len(overlap) * 10 + sum(para_tokens.count(t) for t in overlap)
            score += name_hits * 5
            if score > best_score:
                best_score = score
                best = {
                    "found": True,
                    "path": rel,
                    "paragraph": paragraph,
                    "score": score,
                }
    if not best or best_score <= 0:
        return {
            "found": False,
            "reason": "no matching policy paragraph",
            "question": question,
        }
    return best


@tool
def search_policy(question: str) -> dict:
    """Search DataFlow policy markdown and txt files. Returns the best paragraph or a typed miss."""
    return search_policy_docs(question)
