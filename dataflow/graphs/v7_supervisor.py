"""DataFlow v7: a supervisor with two specialists and one writer.

The desk lead picks the next specialist with structured output and hands
off with Command. Specialists return findings. Only writer issues a
refund or the customer reply. No langgraph-supervisor package.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

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
    "BillingFinding",
    "BillingSpecState",
    "MAX_HANDOFFS",
    "NextStep",
    "PLANT_BAD_RETURN",
    "PolicySpecState",
    "TeamState",
    "add_usage",
    "build_v7_supervisor",
    "builder_for_server",
    "escalate_node",
    "graph",
    "supervise",
    "writer",
]

MAX_HANDOFFS = 4

# Planted bad return for lab 3. Default off. Draft swaps the order id.
PLANT_BAD_RETURN = False

SUPERVISE_SYSTEM = (
    "You are the DataFlow desk lead. "
    "Read the ticket and the notes so far. "
    "Pick exactly one next step. "
    "If notes is empty, do not escalate. Pick billing for a charge, invoice, "
    "duplicate bill, extra charge, or refund ticket. Pick policy for a rules question. "
    "billing: no billing finding is in the notes yet. "
    "policy: you want the customer policy paragraph and do not have it yet. "
    "writer: notes already include a billing finding whose order id appears in the ticket. "
    "The writer is the node that talks to the customer and parks a refund for a person. "
    "Do not pick billing again after a usable billing finding is already in the notes. "
    "escalate: a finding names an order id that is not in the ticket, or a note is "
    "marked rejected. Do not escalate a usable billing finding. Send that to writer. "
    "Do not invent an order id that is not in the ticket."
)

BILLING_SYSTEM = (
    "You are the DataFlow billing specialist. "
    "Read the ticket and the order row. "
    "Return the order id that appears in the ticket, the amount from the row, "
    "whether a refund is eligible, and a short reason. "
    "refund_eligible is true when the customer was billed twice, charged twice, "
    "or is owed a reversal on this order. "
    "Use the order id from the ticket and the order row. Do not invent a different id."
)

REPLY_SYSTEM = (
    "You write the DataFlow customer reply. "
    "Write exactly two sentences from the notes. "
    "Name the order id and what the desk decided. "
    "Do not invent an order, amount, or policy line that is not in the notes."
)

DRAFT_REPLY_SYSTEM = (
    "You draft one sentence for the DataFlow ticket from these notes. "
    "Do not invent an order that is not in the notes."
)


def _last(left, right):
    """Last write wins. Lets two specialists share ticket without colliding."""
    return right if right is not None else left


class TeamState(TypedDict, total=False):
    ticket: Annotated[str, _last]
    notes: Annotated[list, operator.add]
    next_step: str
    handoffs: int
    reply: str
    refund: dict
    usage_tokens: Annotated[int, operator.add]
    usage_log: Annotated[list, operator.add]
    stop_reason: str


class BillingSpecState(TypedDict, total=False):
    ticket: str
    order: dict[str, Any]
    notes: list
    usage_tokens: int
    usage_log: list
    reply: str


class PolicySpecState(TypedDict, total=False):
    ticket: str
    notes: list
    usage_tokens: int
    usage_log: list
    reply: str


class NextStep(BaseModel):
    step: Literal["billing", "policy", "writer", "escalate"] = Field(
        description="Who acts next: a specialist, the writer, or a person"
    )
    why: str = Field(description="One short reason for this handoff")


class BillingFinding(BaseModel):
    order_id: str = Field(description="Order id from the ticket, like DF-1010")
    amount: float = Field(description="Amount on the order row")
    refund_eligible: bool = Field(
        description="True when the customer is owed a refund or reversal"
    )
    reason: str = Field(description="Short reason for the finding")


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


def _usage_dict(result: Any) -> dict[str, Any] | None:
    usage = getattr(result, "usage_metadata", None)
    if usage is None and isinstance(result, dict):
        raw = result.get("raw")
        if raw is not None:
            usage = getattr(raw, "usage_metadata", None)
        if usage is None:
            usage = result.get("usage_metadata")
    if usage is None:
        meta = getattr(result, "response_metadata", None) or {}
        if isinstance(meta, dict):
            usage = meta.get("usage") or meta.get("token_usage")
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def add_usage(state_update: dict, result) -> dict:
    """Read usage from a model result and add it to the running total."""
    usage = _usage_dict(result)
    total = 0
    if usage is not None:
        raw_total = usage.get("total_tokens")
        if raw_total is None:
            inp = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
            out = usage.get("output_tokens") or usage.get("completion_tokens") or 0
            raw_total = int(inp) + int(out)
        total = int(raw_total or 0)
    node = str(state_update.pop("_usage_node", None) or "model")
    delta = int(state_update.get("usage_tokens") or 0) + total
    state_update["usage_tokens"] = delta
    log = list(state_update.get("usage_log") or [])
    log.append({"node": node, "tokens": total})
    state_update["usage_log"] = log
    return state_update


def _parsed_decision(result: Any) -> Any:
    if isinstance(result, dict) and "parsed" in result:
        return result.get("parsed")
    return result


def _step_of(decision: Any) -> str:
    if decision is None:
        return "escalate"
    if hasattr(decision, "step"):
        return str(decision.step)
    if isinstance(decision, dict):
        return str(decision.get("step") or "escalate")
    return "escalate"


def _why_of(decision: Any) -> str:
    if decision is None:
        return ""
    if hasattr(decision, "why"):
        return str(decision.why or "")
    if isinstance(decision, dict):
        return str(decision.get("why") or "")
    return ""


def _finding_payload(decision: Any) -> dict[str, Any]:
    if hasattr(decision, "order_id"):
        return {
            "order_id": str(decision.order_id),
            "amount": float(decision.amount),
            "refund_eligible": bool(decision.refund_eligible),
            "reason": str(decision.reason),
        }
    return {
        "order_id": str(decision.get("order_id") or ""),
        "amount": float(decision.get("amount") or 0),
        "refund_eligible": bool(decision.get("refund_eligible")),
        "reason": str(decision.get("reason") or ""),
    }


def _latest_order_finding(notes: list | None) -> dict[str, Any]:
    for note in reversed(list(notes or [])):
        if not isinstance(note, dict):
            continue
        if note.get("rejected"):
            continue
        if note.get("order_id"):
            return note
    return {}


def _billing_finding(notes: list | None) -> dict[str, Any]:
    for note in reversed(list(notes or [])):
        if isinstance(note, dict) and note.get("source") == "billing":
            return note
    return {}


def _policy_paragraph(notes: list | None) -> str:
    for note in reversed(list(notes or [])):
        if isinstance(note, dict) and note.get("source") == "policy":
            return str(note.get("paragraph") or "")
    return ""


def _order_id_in_ticket(order_id: str, ticket: str) -> bool:
    oid = (order_id or "").strip()
    if not oid:
        return True
    return oid.upper() in (ticket or "").upper()


def _rejected_note(order_id: str) -> dict[str, Any]:
    return {
        "source": "supervise",
        "rejected": True,
        "reason": "finding names " + str(order_id) + " which is not in the ticket",
    }


def run_supervise(
    state: TeamState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
    max_handoffs: int | None = MAX_HANDOFFS,
    plant_loop: bool = False,
) -> Command:
    chat = _resolve_chat(runtime, model)
    ticket = str(state.get("ticket") or "")
    notes = list(state.get("notes") or [])
    structured = chat.with_structured_output(NextStep, include_raw=True)
    result = structured.invoke(
        [
            {"role": "system", "content": SUPERVISE_SYSTEM},
            {
                "role": "user",
                "content": "Ticket:\n" + ticket + "\n\nNotes so far:\n" + str(notes),
            },
        ]
    )
    decision = _parsed_decision(result)
    step = _step_of(decision)
    why = _why_of(decision)
    if step not in {"billing", "policy", "writer", "escalate"}:
        step = "escalate"
        why = why or "unknown next step"

    if plant_loop:
        # Planted, a supervisor that never settles.
        n = int(state.get("handoffs") or 0)
        step = "billing" if n % 2 == 0 else "policy"

    latest = _latest_order_finding(notes)
    bad_id = str(latest.get("order_id") or "")
    rejected = None
    if bad_id and not _order_id_in_ticket(bad_id, ticket):
        rejected = _rejected_note(bad_id)
        step = "escalate"

    stop_reason = str(state.get("stop_reason") or "")
    if (
        rejected is None
        and max_handoffs is not None
        and int(state.get("handoffs") or 0) >= int(max_handoffs)
    ):
        if step not in {"writer", "escalate"}:
            step = "writer"
            stop_reason = "handoff cap " + str(max_handoffs) + " reached"

    update: dict[str, Any] = {
        "next_step": step,
        "handoffs": int(state.get("handoffs") or 0) + 1,
        "_usage_node": "supervise",
    }
    add_usage(update, result)
    if rejected is not None:
        update["notes"] = [rejected]
    if stop_reason:
        update["stop_reason"] = stop_reason
    if why and step == "escalate" and rejected is None:
        update["notes"] = [{"source": "supervise", "why": why}]
    return Command(goto=step, update=update)


def supervise(
    state: TeamState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> Command:
    """Desk lead. Structured next step, then a Command handoff."""
    return run_supervise(
        state,
        runtime,
        model=model,
        max_handoffs=MAX_HANDOFFS,
        plant_loop=False,
    )


def billing_lookup(state: BillingSpecState) -> dict[str, Any]:
    ticket = str(state.get("ticket") or "")
    order = lookup_order_from_ticket(ticket)
    return {"order": order}


def make_billing_draft(model: Any = None, write_reply: bool = False):
    def billing_draft(
        state: BillingSpecState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        chat = _resolve_chat(runtime, model)
        ticket = str(state.get("ticket") or "")
        order = state.get("order") or {}
        structured = chat.with_structured_output(BillingFinding, include_raw=True)
        result = structured.invoke(
            [
                {"role": "system", "content": BILLING_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        "Ticket:\n" + ticket + "\n\nOrder row:\n" + str(order)
                    ),
                },
            ]
        )
        payload = _finding_payload(_parsed_decision(result))
        if PLANT_BAD_RETURN:
            # Planted bad return for lab 3.
            payload["order_id"] = "DF-9999"
        finding = {"source": "billing", **payload}
        update: dict[str, Any] = {
            "notes": [finding],
            "_usage_node": "billing",
        }
        add_usage(update, result)
        if write_reply:
            message = chat.invoke(
                [
                    {"role": "system", "content": DRAFT_REPLY_SYSTEM},
                    {
                        "role": "user",
                        "content": "Ticket:\n" + ticket + "\n\nFinding:\n" + str(finding),
                    },
                ]
            )
            update["reply"] = _content_text(message)
            update["_usage_node"] = "billing"
            add_usage(update, message)
        return update

    return billing_draft


def make_policy_search(model: Any = None, write_reply: bool = False):
    def policy_search_node(
        state: PolicySpecState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        ticket = str(state.get("ticket") or "")
        hit = search_policy.invoke({"question": ticket})
        note = {
            "source": "policy",
            "path": hit.get("path"),
            "paragraph": hit.get("paragraph") or hit.get("reason"),
        }
        update: dict[str, Any] = {
            "notes": [note],
            "usage_tokens": 0,
            "usage_log": [],
        }
        if write_reply:
            chat = _resolve_chat(runtime, model)
            message = chat.invoke(
                [
                    {"role": "system", "content": DRAFT_REPLY_SYSTEM},
                    {
                        "role": "user",
                        "content": "Ticket:\n" + ticket + "\n\nPolicy:\n" + str(note),
                    },
                ]
            )
            update["reply"] = _content_text(message)
            update["_usage_node"] = "policy"
            add_usage(update, message)
        return update

    return policy_search_node


def build_billing_spec(model: Any = None, write_reply: bool = False):
    builder = StateGraph(BillingSpecState, context_schema=DeskContext)
    builder.add_node("lookup", billing_lookup)
    builder.add_node("draft", make_billing_draft(model=model, write_reply=write_reply))
    builder.add_edge(START, "lookup")
    builder.add_edge("lookup", "draft")
    builder.add_edge("draft", END)
    return builder.compile()


def build_policy_spec(model: Any = None, write_reply: bool = False):
    builder = StateGraph(PolicySpecState, context_schema=DeskContext)
    builder.add_node(
        "search_policy",
        make_policy_search(model=model, write_reply=write_reply),
    )
    builder.add_edge(START, "search_policy")
    builder.add_edge("search_policy", END)
    return builder.compile()


def writer(
    state: TeamState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, Any]:
    """The only node that writes reply or issues a refund."""
    notes = list(state.get("notes") or [])
    finding = _billing_finding(notes)
    ticket = str(state.get("ticket") or "")
    refund_record: dict[str, Any] = dict(state.get("refund") or {})
    if finding.get("refund_eligible"):
        order_id = str(finding.get("order_id") or "")
        amount = float(finding.get("amount") or 0)
        policy_line = _policy_paragraph(notes)
        payload = {
            "action": "refund",
            "order_id": order_id,
            "amount": amount,
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
        text = str(decision).strip().lower()
        if isinstance(decision, dict):
            raw_action = decision.get("action") or decision.get("decision")
            text = str(raw_action).strip().lower() if raw_action is not None else ""
        if text == "approve":
            refund_record = issue_refund.invoke(
                {
                    "order_id": order_id,
                    "amount": amount,
                    "reason": "reviewer approved",
                }
            )
        else:
            refund_record = decline_refund.invoke(
                {
                    "order_id": order_id,
                    "reason": "reviewer did not approve",
                }
            )

    chat = _resolve_chat(runtime, model)
    result = chat.invoke(
        [
            {"role": "system", "content": REPLY_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Ticket:\n"
                    + ticket
                    + "\n\nNotes:\n"
                    + str(notes)
                    + "\n\nRefund:\n"
                    + str(refund_record)
                ),
            },
        ]
    )
    update: dict[str, Any] = {
        "reply": _content_text(result),
        "refund": refund_record,
        "_usage_node": "writer",
    }
    add_usage(update, result)
    return update


def escalate_node(state: TeamState) -> dict[str, str]:
    reason = "needs a person"
    found = False
    for note in reversed(list(state.get("notes") or [])):
        if not isinstance(note, dict):
            continue
        if note.get("rejected"):
            reason = str(note.get("reason") or reason)
            found = True
            break
        if note.get("source") == "supervise" and note.get("why"):
            reason = str(note.get("why") or reason)
            found = True
            break
    if not found and state.get("stop_reason"):
        reason = str(state.get("stop_reason"))
    return {"reply": "Escalated to a person: " + reason}


def _parallel_supervise(
    state: TeamState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, Any]:
    chat = _resolve_chat(runtime, model)
    ticket = str(state.get("ticket") or "")
    notes = list(state.get("notes") or [])
    structured = chat.with_structured_output(NextStep, include_raw=True)
    result = structured.invoke(
        [
            {"role": "system", "content": SUPERVISE_SYSTEM},
            {
                "role": "user",
                "content": "Ticket:\n" + ticket + "\n\nNotes so far:\n" + str(notes),
            },
        ]
    )
    update: dict[str, Any] = {
        "next_step": "billing",
        "handoffs": int(state.get("handoffs") or 0) + 1,
        "_usage_node": "supervise",
    }
    add_usage(update, result)
    return update


def build_v7_supervisor(
    checkpointer=None,
    model=None,
    max_handoffs=MAX_HANDOFFS,
    parallel_writers: bool = False,
    plant_loop: bool = False,
    *,
    for_server: bool = False,
):
    """Compile the team. Command handoffs on one thread, unless the lab breaks it.

    for_server=True compiles with no checkpointer. The Agent Server injects
    persistence. Do not use that path in pytest; tests need InMemorySaver.
    """
    if not for_server and checkpointer is None:
        checkpointer = InMemorySaver()
    builder = StateGraph(TeamState, context_schema=DeskContext)
    billing_spec = build_billing_spec(model=model, write_reply=parallel_writers)
    policy_spec = build_policy_spec(model=model, write_reply=parallel_writers)

    if parallel_writers:
        def supervise_node(
            state: TeamState,
            runtime: Runtime[DeskContext] | None = None,
        ) -> dict[str, Any]:
            return _parallel_supervise(state, runtime, model=model)

        builder.add_node("supervise", supervise_node)
        builder.add_node("billing", billing_spec)
        builder.add_node("policy", policy_spec)
        builder.add_edge(START, "supervise")
        builder.add_edge("supervise", "billing")
        builder.add_edge("supervise", "policy")
        builder.add_edge("billing", END)
        builder.add_edge("policy", END)
        if for_server:
            return builder.compile()
        return builder.compile(checkpointer=checkpointer)

    def supervise_node(
        state: TeamState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> Command:
        return run_supervise(
            state,
            runtime,
            model=model,
            max_handoffs=max_handoffs,
            plant_loop=plant_loop,
        )

    def writer_node(
        state: TeamState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return writer(state, runtime, model=model)

    builder.add_node(
        "supervise",
        supervise_node,
        destinations=("billing", "policy", "writer", "escalate"),
    )
    builder.add_node("billing", billing_spec)
    builder.add_node("policy", policy_spec)
    builder.add_node("writer", writer_node)
    builder.add_node("escalate", escalate_node)
    builder.add_edge(START, "supervise")
    builder.add_edge("billing", "supervise")
    builder.add_edge("policy", "supervise")
    builder.add_edge("writer", END)
    builder.add_edge("escalate", END)
    if for_server:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)


def builder_for_server():
    """Compile without a checkpointer. The Agent Server injects persistence."""
    return build_v7_supervisor(for_server=True)


graph = builder_for_server()
