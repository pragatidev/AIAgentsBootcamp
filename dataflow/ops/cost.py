"""Cost and latency report from HTTP trace rows. Tokens and ms, no money."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_http_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def is_fat(row: dict[str, Any]) -> bool:
    tokens = row.get("tokens") or {}
    total = 0
    if isinstance(tokens, dict):
        total = int(tokens.get("total") or 0)
    chars = int(row.get("ticket_chars") or 0)
    return chars >= 1500 or total >= 4000


def render_cost_report(
    rows: list[dict[str, Any]],
    *,
    hide_fat: bool = False,
    note: str = "",
) -> str:
    visible: list[dict[str, Any]] = []
    hidden = 0
    for row in rows:
        if hide_fat and is_fat(row):
            hidden += 1
            continue
        visible.append(row)
    lines = [
        "# DataFlow cost report",
        "",
        "Tokens, milliseconds, and the model id per request. No money column.",
        "",
        "| request_id | model | tokens | ms | ticket_chars | note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in visible:
        tokens = row.get("tokens") or {}
        total = int(tokens.get("total") or 0) if isinstance(tokens, dict) else 0
        fat_note = "fat" if is_fat(row) else ""
        extra = note if is_fat(row) and note else fat_note
        lines.append(
            "| "
            + str(row.get("request_id") or "")
            + " | "
            + str(row.get("model") or "")
            + " | "
            + str(total)
            + " | "
            + str(row.get("ms") or "")
            + " | "
            + str(row.get("ticket_chars") or "")
            + " | "
            + extra
            + " |"
        )
    lines.append("")
    lines.append("rows " + str(len(visible)))
    if hide_fat:
        lines.append("hidden_fat_rows " + str(hidden) + " (report lies if any fat row was dropped)")
    elif any(is_fat(row) for row in visible):
        lines.append("fat row named above. Hiding it would make the report lie.")
    lines.append("")
    return "\n".join(lines)


def write_cost_report(
    http_log: Path,
    dest: Path,
    *,
    hide_fat: bool = False,
    note: str = "",
) -> str:
    rows = load_http_rows(http_log)
    text = render_cost_report(rows, hide_fat=hide_fat, note=note)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return text
