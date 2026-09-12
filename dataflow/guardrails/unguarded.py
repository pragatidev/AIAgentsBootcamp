"""Unguarded and guarded DataFlow desks. Same tools, allowlist on or off."""

from __future__ import annotations

from typing import Any

from dataflow.graphs.rag_tool_cycle import build_rag_tool_cycle
from dataflow.tools.orders import lookup_order
from dataflow.tools.refund import decline_refund, issue_refund
from dataflow.tools.retrieve import retrieve

WRITE_TOOLS = [lookup_order, retrieve, issue_refund, decline_refund]
WRITE_NAMES = {"issue_refund", "decline_refund"}


def first_write_proposal(messages: list) -> dict | None:
    """First write tool the model proposed. None if it did not comply."""
    for msg in messages or []:
        calls = getattr(msg, "tool_calls", None) or []
        if isinstance(msg, dict):
            calls = msg.get("tool_calls") or []
        for call in calls:
            if isinstance(call, dict):
                name = str(call.get("name") or "")
                args = dict(call.get("args") or {})
            else:
                name = str(getattr(call, "name", "") or "")
                args = dict(getattr(call, "args", None) or {})
            if name in WRITE_NAMES:
                return {"tool": name, "args": args}
    return None


def step_types(messages: list) -> list[str]:
    names: list[str] = []
    for msg in messages or []:
        if isinstance(msg, dict):
            names.append(str(msg.get("type") or msg.get("role") or "message"))
            continue
        names.append(str(getattr(msg, "type", None) or msg.__class__.__name__))
    return names


def build_unguarded_desk(*, model: Any = None):
    """Write tools bound, no allowlist. The model can propose a refund."""
    return build_rag_tool_cycle(model=model, tools=list(WRITE_TOOLS))


def build_guarded_desk(actor_id: str, *, model: Any = None):
    """Same tools, allowlist at the port. Anon cannot call a refund tool."""
    from dataflow.guardrails.allowlist import guard_tools

    tools = guard_tools(list(WRITE_TOOLS), actor_id)
    return build_rag_tool_cycle(model=model, tools=tools)
