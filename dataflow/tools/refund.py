"""Pretend refunds. A real row on disk, no real money."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TypedDict

from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

DATAFLOW = Path(__file__).resolve().parents[1]
REFUNDS_PATH = DATAFLOW / "data" / "refunds.jsonl"


def get_refunds_path() -> Path:
    """Path for the refunds ledger. Tests override via env or REFUNDS_PATH."""
    env = os.environ.get("DATAFLOW_REFUNDS_PATH", "").strip()
    if env:
        return Path(env)
    return Path(REFUNDS_PATH)


def read_refunds() -> list[dict]:
    path = get_refunds_path()
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def write_refund(order_id: str, amount: float, reason: str, actor: str = "") -> dict:
    """Append one refunded row. Side effect is the jsonl file, not a bank."""
    row = {
        "refunded": True,
        "order_id": order_id,
        "amount": float(amount),
        "reason": reason,
    }
    if actor:
        row["actor"] = actor
    path = get_refunds_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def actor_from_runtime(*, fallback: str = "") -> str:
    """Read user_id from langgraph.runtime get_runtime. Empty if missing.

    ToolRuntime also works in this venv (see techcorp/tools/accounts.py).
    The refund path uses get_runtime so existing issue_refund.invoke
    calls from v4_hitl do not need a runtime argument.
    DATAFLOW_ACTOR_ADMIN_FALLBACK is the planted miss the lab uses: it
    logs admin and ignores the invoking user.
    """
    if os.environ.get("DATAFLOW_ACTOR_ADMIN_FALLBACK", "").strip():
        return "admin"
    try:
        from langgraph.runtime import get_runtime

        from dataflow.graphs.v1_triage import DeskContext

        runtime = get_runtime(DeskContext)
        ctx = getattr(runtime, "context", None)
        if ctx is None:
            return fallback
        uid = getattr(ctx, "user_id", None) or getattr(ctx, "actor_id", None)
        if uid:
            return str(uid)
    except Exception:
        pass
    return fallback


def actor_from_runtime_admin() -> str:
    """Planted miss: fall back to admin when the id is missing."""
    return actor_from_runtime(fallback="admin")


@tool
def issue_refund(order_id: str, amount: float, reason: str, actor: str = "") -> dict:
    """Issue a pretend refund. Appends one row to refunds.jsonl. No real money."""
    from harness.permissions import apply_write_permission
    from dataflow.ops.tracer import log_actor

    apply_write_permission("issue_refund", order_id)
    acting = actor or actor_from_runtime()
    log_actor(acting or "anon", "issue_refund")
    return write_refund(order_id, amount, reason, actor=acting)


def _parse_resume(decision: Any) -> str:
    if isinstance(decision, dict):
        raw = decision.get("action") or decision.get("decision") or ""
        text = str(raw).strip().lower()
    else:
        text = str(decision).strip().lower()
    if text == "approve":
        return "approve"
    if text in {"reject", "deny", "no"}:
        return "deny"
    return "deny"


class ConfirmState(TypedDict, total=False):
    order_id: str
    amount: float
    reason: str
    actor: str
    refund: dict
    reply: str
    decision: Any


def stash_actor(state: dict[str, Any]) -> dict[str, Any]:
    """Write the invoking user onto state before confirm parks."""
    actor = str(state.get("actor") or "") or actor_from_runtime()
    return {"actor": actor}


def confirm_refund_node(state: dict[str, Any]) -> dict[str, Any]:
    """Park before any write. The write sits after interrupt."""
    order_id = str(state.get("order_id") or "")
    amount = float(state.get("amount") or 0)
    reason = str(state.get("reason") or "")
    actor = str(state.get("actor") or "") or actor_from_runtime()
    from dataflow.ops.tracer import log_actor

    log_actor(actor or "anon", "confirm")
    payload = {
        "action": "refund",
        "order_id": order_id,
        "amount": amount,
        "reason": reason,
        "actor": actor,
    }
    decision = interrupt(payload)
    if _parse_resume(decision) != "approve":
        return {
            "refund": {
                "refunded": False,
                "declined": True,
                "order_id": order_id,
                "reason": "reviewer denied",
            },
            "reply": "Refund declined for order " + order_id,
        }
    record = write_refund(order_id, amount, reason, actor=actor)
    return {
        "refund": record,
        "reply": "Refund issued for order " + order_id,
    }


def confirm_refund_node_planted(state: dict[str, Any]) -> dict[str, Any]:
    """Copy with the write above the interrupt. Lab 11.2 only. Double-charges on resume."""
    order_id = str(state.get("order_id") or "")
    amount = float(state.get("amount") or 0)
    reason = str(state.get("reason") or "")
    actor = str(state.get("actor") or "")
    already = write_refund(
        order_id, amount, reason, actor=actor or "planted"
    )
    payload = {
        "action": "refund",
        "order_id": order_id,
        "amount": amount,
        "reason": reason,
        "actor": actor,
    }
    decision = interrupt(payload)
    return {
        "refund": already,
        "reply": "Refund issued for order " + order_id,
        "decision": decision,
    }


def build_confirm_graph(
    *,
    checkpointer=None,
    write_before_interrupt: bool = False,
):
    if checkpointer is None:
        checkpointer = InMemorySaver()
    from dataflow.graphs.v1_triage import DeskContext

    builder = StateGraph(ConfirmState, context_schema=DeskContext)
    node = confirm_refund_node_planted if write_before_interrupt else confirm_refund_node
    builder.add_node("stash", stash_actor)
    builder.add_node("confirm", node)
    builder.add_edge(START, "stash")
    builder.add_edge("stash", "confirm")
    builder.add_edge("confirm", END)
    return builder.compile(checkpointer=checkpointer)


def resume_confirm(graph: Any, config: dict[str, Any], decision: Any) -> Any:
    return graph.invoke(Command(resume=decision), config)


@tool
def decline_refund(order_id: str, reason: str) -> dict:
    """Decline a refund. Typed miss, no disk write."""
    from harness.permissions import apply_write_permission

    apply_write_permission("decline_refund", order_id)
    return {
        "refunded": False,
        "declined": True,
        "order_id": order_id,
        "reason": reason,
    }
