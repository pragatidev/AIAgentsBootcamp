"""Citations: every claim points at a file."""

from __future__ import annotations

import re
from typing import Any


def format_sources(sources: list[Any]) -> str:
    """One line per source: path, then ' > h2 > h3' when present, then ' row N', then ' lines A to B' when known."""
    lines: list[str] = []
    for item in sources:
        if isinstance(item, str):
            if item.strip():
                lines.append(item.strip())
            continue
        path = str((item or {}).get("source") or "").strip()
        heading = str((item or {}).get("heading_path") or "").strip()
        if not heading:
            parts = [
                str((item or {}).get("h2") or "").strip(),
                str((item or {}).get("h3") or "").strip(),
            ]
            heading = " > ".join(part for part in parts if part)
        line = path
        if heading:
            line = f"{path} > {heading}" if path else heading
        row = (item or {}).get("row")
        if row is not None and row != "":
            line = f"{line} row {row}"
        start = (item or {}).get("line_start")
        if start is not None and line:
            end = (item or {}).get("line_end") or start
            line = f"{line} lines {start} to {end}"
        if line:
            lines.append(line)
    return "\n".join(lines)


_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from", "has", "have",
    "if", "in", "is", "it", "its", "of", "on", "or", "that", "the", "their", "this", "to", "was",
    "with", "you", "your", "will", "within", "not", "no", "yes", "may", "any", "all",
}


def _content_words(text: str) -> set[str]:
    return {word for word in _WORD.findall((text or "").lower()) if word not in _STOP and len(word) > 1}


def _sentences(answer: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (answer or "").strip())
    return [part.strip() for part in parts if part.strip()]


def support_spans(answer: str, passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For each sentence of the answer, the passage sharing the most content words with it.

    A sentence that shares no content word with any passage is flagged
    "unsupported". A check a reviewer can read, not a judge: the faithfulness
    judge of 25.5 stays the semantic check.
    """
    rows: list[dict[str, Any]] = []
    for sentence in _sentences(answer):
        words = _content_words(sentence)
        best: dict[str, Any] | None = None
        best_shared = 0
        for passage in passages or []:
            shared = len(words & _content_words(str(passage.get("text") or "")))
            if shared > best_shared:
                best, best_shared = passage, shared
        row: dict[str, Any] = {"sentence": sentence, "shared_words": best_shared, "unsupported": best is None}
        if best is not None:
            row["source"] = best.get("source")
            row["line_start"] = best.get("line_start")
            row["line_end"] = best.get("line_end")
        rows.append(row)
    return rows


def format_claims(claims: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for claim in claims:
        if claim["unsupported"]:
            lines.append(f"UNSUPPORTED: {claim['sentence']}")
            continue
        where = str(claim.get("source") or "")
        if claim.get("line_start") is not None:
            where += f" lines {claim['line_start']} to {claim.get('line_end') or claim['line_start']}"
        lines.append(f"{claim['sentence']} <- {where}")
    return "\n".join(lines)


def cite(state: dict[str, Any]) -> dict[str, str]:
    """Append a Sources block to the reply. Never invent a source, and say only what the state shows."""
    sources = list(state.get("sources") or [])
    reply = str(state.get("reply") or state.get("answer") or "").rstrip()
    if sources:
        text = reply + "\n\nSources:\n" + format_sources(sources)
    elif state.get("route") == "retrieve" and state.get("passages"):
        text = reply + "\n\nSources: missing (passages were used but none were recorded)"
    else:
        text = (
            reply
            + "\n\nSources: none (this reply did not use the knowledge base)"
        )
    return {"reply": text}


def cite_with_claims(state: dict[str, Any]) -> dict[str, str]:
    """cite, then one Claims line per sentence of the answer, each pointing at the passage and lines it shares words with."""
    out = cite(state)
    kept = list(state.get("graded") or state.get("passages") or [])
    claims = support_spans(str(state.get("answer") or ""), kept)
    if claims:
        out["reply"] = out["reply"] + "\n\nClaims:\n" + format_claims(claims)
    return out


def tool_passages(messages: list[Any], tool_name: str = "retrieve") -> list[dict[str, Any]]:
    """The passages a create_agent desk retrieved: the rows of every `tool_name` tool message, in order, each once.

    A tool message's content is the tool's return value as JSON text. Nothing here
    grades a passage: on that desk the Sources block lists what the tool returned,
    whether or not the answer used it.
    """
    import json

    rows: list[dict[str, Any]] = []
    for message in messages or []:
        if getattr(message, "type", None) != "tool" or getattr(message, "name", None) != tool_name:
            continue
        try:
            found = json.loads(message.content)
        except (TypeError, ValueError):
            continue
        for row in found if isinstance(found, list) else []:
            if isinstance(row, dict) and row.get("source") and row not in rows:
                rows.append(row)
    return rows
