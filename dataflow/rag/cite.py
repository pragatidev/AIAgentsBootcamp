"""Citations: every claim points at a file."""

from __future__ import annotations

from typing import Any


def format_sources(sources: list[Any]) -> str:
    """One line per source: path, then ' > h2 > h3' when present, then ' row N'."""
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
        if line:
            lines.append(line)
    return "\n".join(lines)


def cite(state: dict[str, Any]) -> dict[str, str]:
    """Append a Sources block to the reply. Never invent a source."""
    sources = list(state.get("sources") or [])
    reply = str(state.get("reply") or state.get("answer") or "").rstrip()
    if sources:
        text = reply + "\n\nSources:\n" + format_sources(sources)
    else:
        text = (
            reply
            + "\n\nSources: none (this reply did not use the knowledge base)"
        )
    return {"reply": text}
