"""S12: interrupt before a refund. Lookup is free. Checkpointer required."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from dataflow.tools.orders import lookup_order


class HitlState(TypedDict, total=False):
    ticket: str
    route: str
    order: dict[str, Any]
    decision: str
    reply: str


def classify(state: HitlState) -> dict[str, str]:
    text = state.get("ticket", "").lower()
    if "refund" in text:
        return {"route": "refund"}
    return {"route": "lookup"}


def pick(state: HitlState) -> Literal["lookup", "refund"]:
    return "refund" if state.get("route") == "refund" else "lookup"


def lookup_node(state: HitlState) -> dict[str, Any]:
    order = lookup_order(state.get("ticket", ""))
    return {"order": order, "reply": f"looked up {order.get('order_id', 'none')}"}


def refund_node(state: HitlState) -> dict[str, Any]:
    payload = {
        "action": "refund",
        "ticket": state.get("ticket", ""),
        "question": "Approve this refund?",
    }
    decision = interrupt(payload)
    return {"decision": str(decision), "reply": f"refund {decision}"}


def build_v4_hitl(checkpointer=None):
    graph = StateGraph(HitlState)
    graph.add_node("classify", classify)
    graph.add_node("lookup", lookup_node)
    graph.add_node("refund", refund_node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", pick, {"lookup": "lookup", "refund": "refund"})
    graph.add_edge("lookup", END)
    graph.add_edge("refund", END)
    return graph.compile(checkpointer=checkpointer or MemorySaver())
