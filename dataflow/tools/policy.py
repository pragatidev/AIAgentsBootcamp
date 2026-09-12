"""Customer-facing policy search for the DataFlow desk. No model. No embeddings."""

from __future__ import annotations

import re
from pathlib import Path

from langchain.tools import tool

DATAFLOW = Path(__file__).resolve().parents[1]
WIKI = DATAFLOW / "wiki"
CUSTOMER_FACING = DATAFLOW / "knowledge_base" / "customer_facing"

POLICY_SUFFIXES = {".md", ".markdown", ".txt"}

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

MISS = {
    "found": False,
    "reason": "no customer policy matched",
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
    pending_heading = ""
    for chunk in chunks:
        raw = chunk.strip()
        cleaned = " ".join(raw.split())
        if not cleaned:
            continue
        if re.match(r"^#+ ", raw):
            pending_heading = re.sub(r"^#+\s*", "", cleaned)
            continue
        if pending_heading:
            cleaned = pending_heading + " " + cleaned
            pending_heading = ""
        out.append(cleaned)
    if pending_heading:
        out.append(pending_heading)
    return out


def _customer_policy_files() -> list[Path]:
    files: list[Path] = []
    if WIKI.is_dir():
        files.extend(sorted(WIKI.glob("*.md")))
    if CUSTOMER_FACING.is_dir():
        for path in sorted(CUSTOMER_FACING.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in POLICY_SUFFIXES:
                continue
            files.append(path)
    return files


def search_policy_docs(question: str) -> dict:
    """Keyword search over wiki and customer_facing policy files only."""
    query = _tokens(question)
    if not query:
        return {**MISS, "question": question}
    query_set = set(query)
    best: dict | None = None
    best_score = 0
    for path in _customer_policy_files():
        body = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(DATAFLOW).as_posix()
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
        return {**MISS, "question": question}
    return best


@tool
def search_policy(question: str) -> dict:
    """Search customer-facing DataFlow policy files. Returns the best paragraph or a typed miss."""
    return search_policy_docs(question)
