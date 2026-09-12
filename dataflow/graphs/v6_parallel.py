"""DataFlow v6: fan-out lookup and policy search in one superstep.

Classify runs alone. Then lookup and policy_search share a round.
Their labelled results land through operator.add. draft_reply joins.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext, classify
from dataflow.tools.orders import lookup_order_from_ticket
from dataflow.tools.policy import search_policy

__all__ = [
    "DeskContext",
    "ParallelState",
    "ParallelStateNoReducer",
    "build_v6_parallel",
    "build_v6_parallel_no_reducer",
    "classify",
    "draft_reply",
    "lookup",
    "policy_search",
]

DRAFT_SYSTEM = (
    "You write a DataFlow support reply. "
    "Write exactly two sentences. "
    "The first sentence names the order id and its status. "
    "The second sentence names the policy line the desk found. "
    "Do not invent an order or a policy that is not in the notes."
)


class ParallelState(TypedDict, total=False):
    ticket: str
    route: str
    results: Annotated[list, operator.add]
    reply: str


class ParallelStateNoReducer(TypedDict, total=False):
    ticket: str
    route: str
    results: list
    reply: str


def lookup(state: dict) -> dict[str, Any]:
    """Order lookup. Returns a one item labelled list for the reducer."""
    ticket = state.get("ticket", "")
    order = lookup_order_from_ticket(ticket)
    return {"results": [{"source": "lookup", **order}]}


def policy_search(state: dict) -> dict[str, Any]:
    """Policy search. Returns a one item labelled list for the reducer."""
    ticket = state.get("ticket", "")
    hit = search_policy.invoke({"question": ticket})
    return {"results": [{"source": "policy", **hit}]}


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


def draft_reply(
    state: dict,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, str]:
    """Join node. Reads both labelled results and asks the model for two sentences."""
    chat = model
    if chat is None and runtime is not None:
        ctx = getattr(runtime, "context", None)
        chat = getattr(ctx, "model", None) if ctx is not None else None
    if chat is None:
        chat = get_chat_model()
    results = list(state.get("results") or [])
    lookup_row = next((r for r in results if r.get("source") == "lookup"), {})
    policy_row = next((r for r in results if r.get("source") == "policy"), {})
    ticket = state.get("ticket", "")
    notes = (
        "Ticket:\n"
        + str(ticket)
        + "\n\nOrder lookup:\n"
        + str(lookup_row)
        + "\n\nPolicy line:\n"
        + str(policy_row)
    )
    message = chat.invoke(
        [
            {"role": "system", "content": DRAFT_SYSTEM},
            {"role": "user", "content": notes},
        ]
    )
    return {"reply": _content_text(message)}


def _wire_parallel(builder: StateGraph, model: Any) -> None:
    def classify_node(
        state: dict,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return classify(state, runtime=runtime, model=model)

    def draft_node(
        state: dict,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return draft_reply(state, runtime=runtime, model=model)

    builder.add_node("classify", classify_node)
    builder.add_node("lookup", lookup)
    builder.add_node("policy_search", policy_search)
    builder.add_node("draft_reply", draft_node)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "lookup")
    builder.add_edge("classify", "policy_search")
    builder.add_edge("lookup", "draft_reply")
    builder.add_edge("policy_search", "draft_reply")
    builder.add_edge("draft_reply", END)


def build_v6_parallel(checkpointer=None, model=None):
    """Compile the fan-out desk. Defaults to InMemorySaver so history is readable."""
    if checkpointer is None:
        checkpointer = InMemorySaver()
    builder = StateGraph(ParallelState, context_schema=DeskContext)
    _wire_parallel(builder, model)
    return builder.compile(checkpointer=checkpointer)


def build_v6_parallel_no_reducer(model=None):
    """Same graph, results is a plain list. Two writes in one step collide."""
    builder = StateGraph(ParallelStateNoReducer, context_schema=DeskContext)
    _wire_parallel(builder, model)
    return builder.compile()
