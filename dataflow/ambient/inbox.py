"""Inbox: list parked threads from the checkpointer, resume one at a time."""

from __future__ import annotations

from typing import Any

from langgraph.types import Command


def _thread_ids_from_checkpointer(checkpointer) -> list[str]:
    """Discover thread ids. checkpointer.list(None) lists across threads."""
    seen: set[str] = set()
    ordered: list[str] = []
    for cp in checkpointer.list(None):
        cfg = getattr(cp, "config", None) or {}
        tid = str((cfg.get("configurable") or {}).get("thread_id") or "")
        if tid and tid not in seen:
            seen.add(tid)
            ordered.append(tid)
    return ordered


def list_parked(checkpointer, graph, thread_ids: list[str] | None = None) -> list[dict]:
    """Rows for every thread whose latest state has a pending interrupt."""
    if thread_ids is None:
        thread_ids = _thread_ids_from_checkpointer(checkpointer)
    rows: list[dict] = []
    for thread_id in thread_ids:
        try:
            snap = graph.get_state({"configurable": {"thread_id": thread_id}})
        except Exception:
            continue
        interrupts = getattr(snap, "interrupts", None) or ()
        if not interrupts:
            continue
        payload = interrupts[0].value
        values = snap.values or {}
        parked_at = str(getattr(snap, "created_at", None) or "")
        rows.append(
            {
                "thread_id": thread_id,
                "ticket": values.get("ticket") or "",
                "payload": payload,
                "parked_at": parked_at,
            }
        )
    rows.sort(key=lambda r: (str(r.get("parked_at") or ""), str(r.get("thread_id") or "")))
    return rows


def resolve(graph, thread_id: str, answer, actor: str) -> dict:
    """Resume ONE thread. The actor travels with the Command and the config."""
    if isinstance(answer, dict):
        resume_val: Any = dict(answer)
        resume_val["actor"] = actor
    else:
        resume_val = {"action": answer, "actor": actor}
    config = {"configurable": {"thread_id": thread_id, "actor": actor}}
    result = graph.invoke(
        Command(resume=resume_val, update={"actor": actor}),
        config,
    )
    values = result if isinstance(result, dict) else {}
    snap = graph.get_state(config)
    merged = dict(snap.values or {})
    for key, val in values.items():
        if not str(key).startswith("__"):
            merged[key] = val
    return {
        "thread_id": thread_id,
        "actor": merged.get("actor") or actor,
        "reply": merged.get("reply"),
        "refund": merged.get("refund"),
        "decision": merged.get("decision"),
    }


def render_inbox(rows) -> str:
    """Plain text list a reviewer can read."""
    if not rows:
        return "(empty)"
    lines: list[str] = []
    for row in rows:
        lines.append(
            str(row.get("thread_id") or "")
            + "  parked_at="
            + str(row.get("parked_at") or "")
        )
        ticket = str(row.get("ticket") or "")
        if ticket:
            lines.append("  ticket: " + ticket)
        payload = row.get("payload")
        if payload is not None:
            lines.append("  payload: " + str(payload))
    return "\n".join(lines)
