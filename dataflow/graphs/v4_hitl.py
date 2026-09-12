"""DataFlow v4: park a refund, let a person answer, then write.

Lookup and policy are free reads. Refund calls interrupt before any
side effect. Classify calls the model from config. No keyword stand-in.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext
from dataflow.tools.orders import lookup_order_from_ticket
from dataflow.tools.policy import search_policy
from dataflow.tools.refund import decline_refund, issue_refund

__all__ = [
    "DeskContext",
    "HitlDecision",
    "HitlState",
    "build_v4_hitl",
    "classify",
    "lookup_node",
    "pick_route",
    "policy_node",
    "refund_node",
    "refund_node_planted",
    "resume_with",
]

CLASSIFY_SYSTEM = (
    "You route DataFlow support tickets. "
    "Pick exactly one route. "
    "refund: the customer wants money back, a return refund, or a charge reversed. "
    "lookup: the customer asks where an order is, its status, or tracking, "
    "and is not asking to move money. "
    "policy: general rules with no named refund, such as the return window "
    "or shipping SLA."
)


class HitlState(TypedDict, total=False):
    ticket: str
    route: str
    order: dict[str, Any]
    policy: dict[str, Any]
    decision: Any
    reply: str
    refund: dict[str, Any]
    refund_amount: float | None


class HitlDecision(BaseModel):
    route: Literal["lookup", "refund", "policy"] = Field(
        description="lookup and policy are free reads; refund parks for a person"
    )


def classify(
    state: HitlState,
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
    structured = chat.with_structured_output(HitlDecision)
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


def pick_route(state: HitlState) -> Literal["lookup", "refund", "policy"]:
    route = str(state.get("route") or "")
    if route in {"lookup", "refund", "policy"}:
        return route  # type: ignore[return-value]
    return "lookup"


def lookup_node(state: HitlState) -> dict[str, Any]:
    """A read. Free. Never parks."""
    ticket = state.get("ticket", "")
    order = lookup_order_from_ticket(ticket)
    if order.get("found"):
        reply = (
            f"looked up {order['order_id']}. "
            f"Order {order['order_id']} is {order['status']}. "
            f"Item: {order['item']}."
        )
    else:
        reason = order.get("reason", "no order")
        reply = f"looked up none. I could not find that order ({reason})."
    return {"order": order, "reply": reply}


def policy_node(state: HitlState) -> dict[str, Any]:
    """A read. Free. Never parks."""
    ticket = state.get("ticket", "")
    hit = search_policy.invoke({"question": ticket})
    if hit.get("found"):
        reply = f"From {hit['path']}: {hit['paragraph']}"
    else:
        reason = hit.get("reason", "no customer policy matched")
        reply = f"I could not find a customer policy ({reason})."
    return {"policy": hit, "reply": reply}


def _parse_decision(decision: Any, default_amount: float) -> tuple[str, float]:
    """Map the reviewer's answer to an action and an amount.

    Approve only on an explicit approve. Reject on reject/deny/no.
    Any other answer is unclear: no write, no decline.
    """
    if isinstance(decision, dict):
        raw_action = decision.get("action")
        if raw_action is None:
            raw_action = decision.get("decision")
        action = str(raw_action).strip().lower() if raw_action is not None else ""
        if "amount" in decision and decision["amount"] is not None:
            amount = float(decision["amount"])
        else:
            amount = default_amount
        if action == "approve":
            return "approve", amount
        if action in {"reject", "deny", "no"}:
            return "reject", amount
        return "unclear", amount
    text = str(decision).strip().lower()
    if text == "approve":
        return "approve", default_amount
    if text in {"reject", "deny", "no"}:
        return "reject", default_amount
    return "unclear", default_amount


def refund_node(state: HitlState) -> dict[str, Any]:
    """Park before any write. The write sits after interrupt."""
    ticket = state.get("ticket", "")
    order = lookup_order_from_ticket(ticket)
    hit = search_policy.invoke({"question": ticket})
    if hit.get("found"):
        policy_line = str(hit.get("paragraph") or "")
    else:
        policy_line = str(hit.get("reason") or "no customer policy matched")
    amount = float(state.get("refund_amount") or order.get("amount") or 0)
    order_id = str(order.get("order_id") or "")
    payload = {
        "action": "refund",
        "ticket": ticket,
        "order_id": order_id,
        "amount": amount,
        "amount_source": "state" if state.get("refund_amount") else "order",
        "policy": policy_line,
        "question": (
            "Approve this refund of "
            + str(amount)
            + " on order "
            + order_id
            + "?"
        ),
    }
    decision = interrupt(payload)
    # The write is after interrupt. The node re-runs from its start on resume,
    # so a write before this line would issue the refund before anyone approved,
    # then issue it again when the reviewer answers.
    action, paid = _parse_decision(decision, amount)
    if action == "unclear":
        record = {
            "refunded": False,
            "unclear": True,
            "order_id": order_id,
            "answer": decision,
        }
        reply = (
            "Refund not issued for order "
            + order_id
            + ": reviewer answer not understood ("
            + str(decision)
            + ")"
        )
        return {
            "order": order,
            "decision": decision,
            "refund": record,
            "reply": reply,
        }
    if action == "reject":
        record = decline_refund.invoke(
            {
                "order_id": order_id,
                "reason": "reviewer rejected the refund",
            }
        )
        reply = (
            "Refund declined for order "
            + order_id
            + ". Reason: "
            + str(record.get("reason"))
        )
        return {
            "order": order,
            "decision": decision,
            "refund": record,
            "reply": reply,
        }
    record = issue_refund.invoke(
        {
            "order_id": order_id,
            "amount": paid,
            "reason": "reviewer approved",
        }
    )
    reply = (
        "Refund issued for order "
        + order_id
        + ". Amount: "
        + str(record.get("amount"))
        + "."
    )
    return {
        "order": order,
        "decision": decision,
        "refund": record,
        "reply": reply,
    }


# PLANTED TRAP for lab 11.2. The write sits before the interrupt, so it
# runs when the node first executes, before any person answered, and the
# node re-runs from its top on resume, so it runs again. Never ship this
# shape.
def refund_node_planted(state: HitlState) -> dict[str, Any]:
    """Copy of refund_node with the write before interrupt. Lab 11.2 only."""
    ticket = state.get("ticket", "")
    order = lookup_order_from_ticket(ticket)
    hit = search_policy.invoke({"question": ticket})
    if hit.get("found"):
        policy_line = str(hit.get("paragraph") or "")
    else:
        policy_line = str(hit.get("reason") or "no customer policy matched")
    amount = float(state.get("refund_amount") or order.get("amount") or 0)
    order_id = str(order.get("order_id") or "")
    payload = {
        "action": "refund",
        "ticket": ticket,
        "order_id": order_id,
        "amount": amount,
        "amount_source": "state" if state.get("refund_amount") else "order",
        "policy": policy_line,
        "question": (
            "Approve this refund of "
            + str(amount)
            + " on order "
            + order_id
            + "?"
        ),
    }
    already = issue_refund.invoke(
        {
            "order_id": order_id,
            "amount": amount,
            "reason": "written before anyone approved",
        }
    )
    decision = interrupt(payload)
    action, paid = _parse_decision(decision, amount)
    if action == "unclear":
        record = {
            "refunded": False,
            "unclear": True,
            "order_id": order_id,
            "answer": decision,
        }
        reply = (
            "Refund not issued for order "
            + order_id
            + ": reviewer answer not understood ("
            + str(decision)
            + ")"
        )
        return {
            "order": order,
            "decision": decision,
            "refund": record,
            "reply": reply,
        }
    if action == "reject":
        record = decline_refund.invoke(
            {
                "order_id": order_id,
                "reason": "reviewer rejected the refund",
            }
        )
        reply = (
            "Refund declined for order "
            + order_id
            + ". Reason: "
            + str(record.get("reason"))
        )
        return {
            "order": order,
            "decision": decision,
            "refund": record,
            "reply": reply,
        }
    reply = (
        "Refund issued for order "
        + order_id
        + ". Amount: "
        + str(already.get("amount"))
        + "."
    )
    return {
        "order": order,
        "decision": decision,
        "refund": already,
        "reply": reply,
    }


def resume_with(graph: Any, config: dict[str, Any], decision: Any) -> Any:
    """Resume a parked thread with the reviewer's answer."""
    return graph.invoke(Command(resume=decision), config)


def build_v4_hitl(
    checkpointer=None,
    model=None,
    interrupt_before=None,
    write_before_interrupt: bool = False,
):
    """Compile the desk. Defaults to InMemorySaver when checkpointer is None."""
    if checkpointer is None:
        checkpointer = InMemorySaver()

    builder = StateGraph(HitlState, context_schema=DeskContext)

    def classify_node(
        state: HitlState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return classify(state, runtime=runtime, model=model)

    refund_fn = refund_node_planted if write_before_interrupt else refund_node
    builder.add_node("classify", classify_node)
    builder.add_node("lookup", lookup_node)
    builder.add_node("policy", policy_node)
    builder.add_node("refund", refund_fn)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        pick_route,
        {
            "lookup": "lookup",
            "refund": "refund",
            "policy": "policy",
        },
    )
    builder.add_edge("lookup", END)
    builder.add_edge("policy", END)
    builder.add_edge("refund", END)
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before or [],
    )
