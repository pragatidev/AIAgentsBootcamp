"""DataFlow v1: classify, lookup, reply.

A line, not branches. Classify calls the model from config.
Lookup is plain Python over orders.json. Reply writes one sentence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from config import get_chat_model

ORDERS_PATH = Path(__file__).resolve().parents[1] / "data" / "orders.json"

CLASSIFY_SYSTEM = (
    "You route DataFlow support tickets. "
    "Pick exactly one route. "
    "orders: the ticket names an order id, or asks about status, refund, "
    "delivery, return of a specific order, or billing for an order. "
    "policy: general rules with no specific order, such as the return window, "
    "shipping SLA, account, or password. "
    "escalate: angry customer, legal threat, repeated failure, or a human is needed."
)


class TriageState(TypedDict, total=False):
    ticket: str
    route: str
    order: dict[str, Any]
    reply: str


class RouteDecision(BaseModel):
    route: Literal["orders", "policy", "escalate"] = Field(
        description="Which desk should own this ticket"
    )


@dataclass
class DeskContext:
    model: Any = None
    customer_id: str = "anon"


def classify(
    state: TriageState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, str]:
    """Call the chat model. No keyword stand-in."""
    chat = model
    if chat is None and runtime is not None:
        ctx = getattr(runtime, "context", None)
        chat = getattr(ctx, "model", None) if ctx is not None else None
    if chat is None:
        chat = get_chat_model()
    structured = chat.with_structured_output(RouteDecision)
    ticket = state.get("ticket", "")
    decision = structured.invoke(
        [
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": ticket},
        ]
    )
    if hasattr(decision, "route"):
        route = decision.route
    else:
        route = decision["route"]
    return {"route": str(route)}


def lookup(state: TriageState) -> dict[str, Any]:
    """Plain Python over dataflow/data/orders.json. No model."""
    ticket = state.get("ticket", "")
    orders = json.loads(ORDERS_PATH.read_text(encoding="utf-8"))
    match = re.search(r"DF-\d+", ticket.upper())
    if not match:
        return {"order": {"found": False, "reason": "no order id in the ticket"}}
    order_id = match.group(0)
    row = orders.get(order_id)
    if not row:
        return {
            "order": {
                "found": False,
                "order_id": order_id,
                "reason": "unknown order",
            }
        }
    return {"order": {"found": True, "order_id": order_id, **row}}


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


def build_v1_triage(*, model: Any = None):
    builder = StateGraph(TriageState, context_schema=DeskContext)

    def classify_node(
        state: TriageState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return classify(state, runtime=runtime, model=model)

    builder.add_node("classify", classify_node)
    builder.add_node("lookup", lookup)
    builder.add_node("reply", reply)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "lookup")
    builder.add_edge("lookup", "reply")
    builder.add_edge("reply", END)
    return builder.compile()
