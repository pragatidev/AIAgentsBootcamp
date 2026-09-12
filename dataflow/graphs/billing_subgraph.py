"""Billing as a subgraph: private invoice and adjustment, shared ticket and reply.

The billing graph compiles on its own. The parent desk adds it as one node.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext
from dataflow.graphs.v2_route import orders_desk, policy_desk
from dataflow.tools.orders import lookup_order_from_ticket

__all__ = [
    "BillingFinding",
    "BillingState",
    "DeskRoute",
    "DeskState",
    "billing_graph",
    "build_billing_graph",
    "build_desk_with_billing",
]

FINDING_SYSTEM = (
    "You read a DataFlow billing ticket and the order row. "
    "duplicate_charge is true only when the customer was billed twice "
    "or charged twice for the same order. "
    "missing_tax_line is true only when the invoice is missing a tax line. "
    "disputed_fee is true only when they dispute a fee such as restocking. "
    "Decide from the ticket meaning. Do not use a single keyword rule."
)

DESK_SYSTEM = (
    "You route DataFlow support tickets. "
    "Pick exactly one route. "
    "billing: billed twice, duplicate charge, invoice, tax line, "
    "restocking fee, or an adjustment on a charge. "
    "orders: status, delivery, return, or refund of a named order "
    "that is not a billing dispute. "
    "policy: general rules with no named order billing issue, "
    "such as the return window or shipping SLA."
)

REPLY_SYSTEM = (
    "You write a DataFlow billing reply. "
    "Two short sentences. "
    "Name the order id, the amount, and what the invoice shows. "
    "Do not invent a duplicate charge when duplicate_charge is false. "
    "Do not promise an adjustment when adjustment is 0."
)


class BillingState(TypedDict, total=False):
    ticket: str
    reply: str
    invoice: dict
    adjustment: float


class DeskState(TypedDict, total=False):
    ticket: str
    route: str
    reply: str
    order: dict[str, Any]
    policy: dict[str, Any]


class BillingFinding(BaseModel):
    duplicate_charge: bool = Field(
        description="True when the customer was billed twice for the order"
    )
    missing_tax_line: bool = Field(
        description="True when the invoice is missing a tax line"
    )
    disputed_fee: bool = Field(
        description="True when the customer disputes a fee such as restocking"
    )


class DeskRoute(BaseModel):
    route: Literal["billing", "orders", "policy"] = Field(
        description="Which desk should own this ticket"
    )


def _resolve_chat(
    runtime: Runtime[DeskContext] | None,
    model: Any,
) -> Any:
    chat = model
    if chat is None and runtime is not None:
        ctx = getattr(runtime, "context", None)
        chat = getattr(ctx, "model", None) if ctx is not None else None
    if chat is None:
        chat = get_chat_model()
    return chat


def _content_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(p for p in parts if p)
    if content is None:
        return ""
    return str(content)


def _finding_payload(decision: Any) -> dict[str, bool]:
    if hasattr(decision, "duplicate_charge"):
        return {
            "duplicate_charge": bool(decision.duplicate_charge),
            "missing_tax_line": bool(decision.missing_tax_line),
            "disputed_fee": bool(decision.disputed_fee),
        }
    return {
        "duplicate_charge": bool(decision["duplicate_charge"]),
        "missing_tax_line": bool(decision["missing_tax_line"]),
        "disputed_fee": bool(decision["disputed_fee"]),
    }


def fetch_invoice(
    state: BillingState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, Any]:
    """Look up the order and ask the model for the billing finding."""
    chat = _resolve_chat(runtime, model)
    ticket = state.get("ticket", "")
    order = lookup_order_from_ticket(ticket)
    structured = chat.with_structured_output(BillingFinding)
    decision = structured.invoke(
        [
            {"role": "system", "content": FINDING_SYSTEM},
            {
                "role": "user",
                "content": "Ticket:\n" + str(ticket) + "\n\nOrder:\n" + str(order),
            },
        ]
    )
    flags = _finding_payload(decision)
    invoice = {
        "order_id": order.get("order_id"),
        "amount": order.get("amount"),
        "status": order.get("status"),
        "item": order.get("item"),
        "found": order.get("found"),
        **flags,
    }
    return {"invoice": invoice}


def decide_adjustment(state: BillingState) -> dict[str, float]:
    """adjustment is the order amount when duplicate_charge is true, else 0."""
    invoice = state.get("invoice") or {}
    amount = float(invoice.get("amount") or 0)
    if invoice.get("duplicate_charge"):
        return {"adjustment": amount}
    return {"adjustment": 0.0}


def approve_adjustment(state: BillingState) -> dict[str, str]:
    """Park only when there is an adjustment. Write the reply after resume."""
    adjustment = float(state.get("adjustment") or 0)
    if adjustment <= 0:
        return {}
    invoice = state.get("invoice") or {}
    order_id = str(invoice.get("order_id") or "")
    decision = interrupt(
        {
            "action": "adjust",
            "order_id": order_id,
            "amount": adjustment,
            "question": (
                "Approve this adjustment of "
                + str(adjustment)
                + " on order "
                + order_id
                + "?"
            ),
        }
    )
    text = str(decision).strip().lower()
    if text == "approve":
        return {
            "reply": (
                "Adjustment of " + str(adjustment) + " approved on " + order_id
            )
        }
    return {"reply": "declined"}


def reply_billing(
    state: BillingState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, str]:
    """No adjustment. Explain the invoice."""
    chat = _resolve_chat(runtime, model)
    invoice = state.get("invoice") or {}
    ticket = state.get("ticket", "")
    message = chat.invoke(
        [
            {"role": "system", "content": REPLY_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Ticket:\n"
                    + str(ticket)
                    + "\n\nInvoice:\n"
                    + str(invoice)
                    + "\n\nadjustment: "
                    + str(state.get("adjustment"))
                ),
            },
        ]
    )
    return {"reply": _content_text(message)}


def pick_after_decision(state: BillingState) -> Literal["approve_adjustment", "reply_billing"]:
    if float(state.get("adjustment") or 0) > 0:
        return "approve_adjustment"
    return "reply_billing"


def make_billing_builder(model: Any = None) -> StateGraph:
    builder = StateGraph(BillingState, context_schema=DeskContext)

    def fetch_node(
        state: BillingState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return fetch_invoice(state, runtime=runtime, model=model)

    def reply_node(
        state: BillingState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return reply_billing(state, runtime=runtime, model=model)

    builder.add_node("fetch_invoice", fetch_node)
    builder.add_node("decide_adjustment", decide_adjustment)
    builder.add_node("approve_adjustment", approve_adjustment)
    builder.add_node("reply_billing", reply_node)
    builder.add_edge(START, "fetch_invoice")
    builder.add_edge("fetch_invoice", "decide_adjustment")
    builder.add_conditional_edges(
        "decide_adjustment",
        pick_after_decision,
        {
            "approve_adjustment": "approve_adjustment",
            "reply_billing": "reply_billing",
        },
    )
    builder.add_edge("approve_adjustment", END)
    builder.add_edge("reply_billing", END)
    return builder


billing_builder = make_billing_builder()
billing_graph = billing_builder.compile()


def build_billing_graph(checkpointer=None, model=None):
    """Compile the billing subgraph. Used by tests and by the parent builder."""
    return make_billing_builder(model=model).compile(checkpointer=checkpointer)


def classify_desk(
    state: DeskState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, str]:
    chat = _resolve_chat(runtime, model)
    structured = chat.with_structured_output(DeskRoute)
    ticket = state.get("ticket", "")
    decision = structured.invoke(
        [
            {"role": "system", "content": DESK_SYSTEM},
            {"role": "user", "content": ticket},
        ]
    )
    if hasattr(decision, "route"):
        route = decision.route
    else:
        route = decision["route"]
    return {"route": str(route)}


def pick_desk(state: DeskState) -> Literal["billing", "orders", "policy"]:
    route = str(state.get("route") or "")
    if route in {"billing", "orders", "policy"}:
        return route  # type: ignore[return-value]
    return "policy"


def build_desk_with_billing(
    checkpointer=None,
    model=None,
    subgraph_checkpointer=None,
):
    """Parent desk. subgraph_checkpointer is None, True, or False on billing compile."""
    if checkpointer is None:
        checkpointer = InMemorySaver()
    builder = StateGraph(DeskState, context_schema=DeskContext)

    def classify_node(
        state: DeskState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return classify_desk(state, runtime=runtime, model=model)

    builder.add_node("classify", classify_node)
    if subgraph_checkpointer is None and model is None:
        builder.add_node("billing", billing_graph)
    else:
        compiled_billing = build_billing_graph(
            checkpointer=subgraph_checkpointer,
            model=model,
        )
        builder.add_node("billing", compiled_billing)
    builder.add_node("orders", orders_desk)
    builder.add_node("policy", policy_desk)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        pick_desk,
        {
            "billing": "billing",
            "orders": "orders",
            "policy": "policy",
        },
    )
    builder.add_edge("billing", END)
    builder.add_edge("orders", END)
    builder.add_edge("policy", END)
    return builder.compile(checkpointer=checkpointer)
