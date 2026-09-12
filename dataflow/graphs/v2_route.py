"""DataFlow v2: classify, then a labeled route.

Classify calls the model from config with RouteDecision.
pick_route reads state and labels the three desks.
Each desk looks up, searches, or parks, then writes a reply.
"""

from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from dataflow.graphs.v1_triage import DeskContext, classify
from dataflow.tools.escalate import escalate
from dataflow.tools.orders import lookup_order
from dataflow.tools.policy import search_policy

__all__ = [
    "DeskContext",
    "TriageState",
    "build_v2_route",
    "classify",
    "escalate_desk",
    "orders_desk",
    "pick_route",
    "policy_desk",
]


class TriageState(TypedDict, total=False):
    ticket: str
    route: str
    order: dict[str, Any]
    policy: dict[str, Any]
    escalation: dict[str, Any]
    reply: str


def pick_route(state: TriageState) -> Literal["orders", "policy", "escalate"]:
    route = str(state.get("route") or "")
    if route in {"orders", "policy", "escalate"}:
        return route  # type: ignore[return-value]
    return "escalate"


def orders_desk(state: TriageState) -> dict[str, Any]:
    ticket = state.get("ticket", "")
    match = re.search(r"DF-\d+", ticket.upper())
    order_id = match.group(0) if match else ""
    order = lookup_order.invoke({"order_id": order_id or ticket})
    if order.get("found"):
        reply = (
            f"Order {order['order_id']} is {order['status']}. "
            f"Item: {order['item']}."
        )
    else:
        reason = order.get("reason", "no order")
        reply = f"I could not find that order ({reason})."
    return {"order": order, "reply": reply}


def policy_desk(state: TriageState) -> dict[str, Any]:
    ticket = state.get("ticket", "")
    hit = search_policy.invoke({"question": ticket})
    if hit.get("found"):
        reply = f"From {hit['path']}: {hit['paragraph']}"
    else:
        reason = hit.get("reason", "no customer policy matched")
        reply = f"I could not find a customer policy ({reason})."
    return {"policy": hit, "reply": reply}


def escalate_desk(state: TriageState) -> dict[str, Any]:
    ticket = state.get("ticket", "")
    parked = escalate.invoke({"reason": ticket})
    reply = (
        f"Ticket parked for a human. Queue: {parked.get('queue')}. "
        f"Reason: {parked.get('reason')}"
    )
    return {"escalation": parked, "reply": reply}


def build_v2_route(*, model: Any = None):
    builder = StateGraph(TriageState, context_schema=DeskContext)

    def classify_node(
        state: TriageState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return classify(state, runtime=runtime, model=model)

    builder.add_node("classify", classify_node)
    builder.add_node("orders_desk", orders_desk)
    builder.add_node("policy_desk", policy_desk)
    builder.add_node("escalate_desk", escalate_desk)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        pick_route,
        {
            "orders": "orders_desk",
            "policy": "policy_desk",
            "escalate": "escalate_desk",
        },
    )
    builder.add_edge("orders_desk", END)
    builder.add_edge("policy_desk", END)
    builder.add_edge("escalate_desk", END)
    return builder.compile()
