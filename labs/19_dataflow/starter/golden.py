"""Eight golden rows. The plant: refuse rows return a fluent miss until you stop using the plant."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
GOLDEN_PATH = HERE / "golden.jsonl"

PLANTED_FLUENT = {
    "refuse-student": "Yes, every desk lamp has a lifetime warranty for students.",
    "refuse-coffee": "Yes, DataFlow sells coffee beans in the shop.",
}

REFUSE_LINE = "I do not have that in the knowledge base"


def load_rows(path: Path | None = None) -> list[dict[str, Any]]:
    target = Path(path) if path is not None else GOLDEN_PATH
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def planted_fluent(row: dict[str, Any]) -> str:
    key = str(row.get("id") or "")
    if key in PLANTED_FLUENT:
        return PLANTED_FLUENT[key]
    return "Yes, DataFlow offers that."


def run_row(
    row: dict[str, Any],
    graph: Any = None,
    *,
    use_plant: bool = True,
    model: Any = None,
    thread_id: str = "golden",
) -> dict[str, Any]:
    """Score one golden row.

    use_plant=True is the planted fluent miss on refuse rows. The starter
    suite has no refuse test, so this still looks green.
    """
    kind = str(row.get("kind") or "")
    ticket = str(row.get("input") or "")
    if use_plant and kind == "refuse":
        return {
            "id": row.get("id"),
            "kind": kind,
            "reply": planted_fluent(row),
            "route": "answer",
            "planted": True,
        }
    if graph is None:
        from graph import build_desk, run_ticket

        return run_ticket(ticket, model=model, thread_id=thread_id)
    cfg = {"configurable": {"thread_id": thread_id}}
    out = graph.invoke({"ticket": ticket, "question": ticket}, cfg)
    if not isinstance(out, dict):
        out = {"reply": str(out)}
    out["id"] = row.get("id")
    out["kind"] = kind
    out["planted"] = False
    return out


def reply_text(out: dict[str, Any]) -> str:
    return str(out.get("reply") or out.get("answer") or "")
