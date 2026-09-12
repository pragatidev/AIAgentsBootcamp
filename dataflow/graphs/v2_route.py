"""S9: labeled branches. Orders, policy, or escalate. No model."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from dataflow.tools.escalate import escalate_to_human
from dataflow.tools.orders import lookup_order
from dataflow.tools.policy import read_policy


class RouteState(TypedDict, total=False):
    ticket: str
    route: str
    result: dict[str, Any]


def classify(state: RouteState) -> dict[str, str]:
    text = state.get("ticket", "").lower()
    if "human" in text or "manager" in text:
        return {"route": "escalate"}
    if "return" in text or "refund" in text or "df-" in text:
        return {"route": "orders"}
    return {"route": "policy"}


def route_after_classify(state: RouteState) -> Literal["orders", "policy", "escalate"]:
    return state.get("route") or "policy"  # type: ignore[return-value]


def orders_node(state: RouteState) -> dict[str, Any]:
    return {"result": lookup_order(state.get("ticket", ""))}


def policy_node(state: RouteState) -> dict[str, Any]:
    return {"result": read_policy(state.get("ticket", ""))}


def escalate_node(state: RouteState) -> dict[str, Any]:
    return {"result": escalate_to_human(state.get("ticket", ""))}


def build_v2_route():
    graph = StateGraph(RouteState)
    graph.add_node("classify", classify)
    graph.add_node("orders", orders_node)
    graph.add_node("policy", policy_node)
    graph.add_node("escalate", escalate_node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"orders": "orders", "policy": "policy", "escalate": "escalate"},
    )
    graph.add_edge("orders", END)
    graph.add_edge("policy", END)
    graph.add_edge("escalate", END)
    return graph.compile()
