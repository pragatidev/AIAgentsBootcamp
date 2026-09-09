"""Northstar v1: classify, lookup, reply.

A line, not branches. S9 adds conditional edges.
No model. Classify reads the ticket text.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from northstar.tools.orders import lookup_order


class TriageState(TypedDict, total=False):
    ticket: str
    route: str
    order: dict[str, Any]
    reply: str


def classify(state: TriageState) -> dict[str, str]:
    """Stand-in for the model. Return tickets go to orders. Else policy."""
    text = state.get("ticket", "").lower()
    if "return" in text or "refund" in text or "ns-" in text:
        return {"route": "orders"}
    return {"route": "policy"}


def lookup(state: TriageState) -> dict[str, Any]:
    ticket = state.get("ticket", "")
    return {"order": lookup_order(ticket)}


def reply(state: TriageState) -> dict[str, str]:
    order = state.get("order") or {}
    if order.get("found"):
        return {
            "reply": (
                f"Order {order['order_id']} is {order['status']}. "
                f"Item: {order['item']}."
            )
        }
    reason = order.get("reason", "no order")
    return {"reply": f"I could not find that order ({reason})."}


def build_v1_triage():
    graph = StateGraph(TriageState)
    graph.add_node("classify", classify)
    graph.add_node("lookup", lookup)
    graph.add_node("reply", reply)
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "lookup")
    graph.add_edge("lookup", "reply")
    graph.add_edge("reply", END)
    return graph.compile()
