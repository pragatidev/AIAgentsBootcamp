"""Capstone desk graph. Node bodies that decide are TODO stubs until filled."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

FILL_FROM_REPO = False  # TODO fill: import and delegate from the finished package


class DeskState(TypedDict, total=False):
    ticket: str
    question: str
    route: str
    order: dict[str, Any]
    passages: list[dict[str, Any]]
    graded: list[dict[str, Any]]
    reply: str
    answer: str
    sources: list[dict[str, Any]]
    refund: dict[str, Any]
    decision: Any
    refund_amount: float | None
    actor: str


def classify(state: DeskState, runtime: Any = None, *, model: Any = None) -> dict[str, str]:
    """TODO classify: call the model from config and return a route."""
    if not FILL_FROM_REPO:
        raise NotImplementedError("call the model from config and return a route")
    from dataflow.graphs.v4_hitl import classify as _classify

    ticket = state.get("ticket") or state.get("question") or ""
    return _classify({"ticket": ticket}, runtime=runtime, model=model)


def lookup_node(state: DeskState) -> dict[str, Any]:
    """TODO lookup: look up the order named in the ticket."""
    if not FILL_FROM_REPO:
        raise NotImplementedError("look up the order named in the ticket")
    from dataflow.graphs.v4_hitl import lookup_node as _lookup

    ticket = state.get("ticket") or state.get("question") or ""
    return _lookup({"ticket": ticket})


def generate(state: DeskState, runtime: Any = None, *, model: Any = None) -> dict[str, Any]:
    """TODO generate: answer only from kept passages."""
    if not FILL_FROM_REPO:
        raise NotImplementedError("answer only from kept passages")
    from dataflow.graphs.rag_graph import generate as _generate

    question = state.get("question") or state.get("ticket") or ""
    mapped = dict(state)
    mapped["question"] = question
    mapped.setdefault("graded", state.get("passages") or [])
    return _generate(mapped, runtime=runtime, model=model)


def refuse(state: DeskState) -> dict[str, Any]:
    """TODO refuse: say the knowledge base has nothing."""
    if not FILL_FROM_REPO:
        raise NotImplementedError("say the knowledge base has nothing")
    from dataflow.graphs.rag_graph import refuse as _refuse

    question = state.get("question") or state.get("ticket") or ""
    return _refuse(
        {
            "question": question,
            "rewritten_question": state.get("rewritten_question"),
        }
    )


def retrieve_node(state: DeskState) -> dict[str, Any]:
    """Wired retrieve. Passages become graded so generate can use them."""
    from dataflow.graphs.rag_graph import retrieve_node as _retrieve

    question = (
        state.get("rewritten_question")
        or state.get("question")
        or state.get("ticket")
        or ""
    )
    out = _retrieve({"question": question, "rewritten_question": state.get("rewritten_question")})
    passages = list(out.get("passages") or [])
    out["graded"] = passages
    return out


def refund_node(state: DeskState) -> dict[str, Any]:
    """Wired refund park. The write sits after interrupt."""
    from dataflow.graphs.v4_hitl import refund_node as _refund

    ticket = state.get("ticket") or state.get("question") or ""
    mapped = dict(state)
    mapped["ticket"] = ticket
    return _refund(mapped)


def pick_route(state: DeskState) -> Literal["lookup", "refund", "retrieve"]:
    route = str(state.get("route") or "")
    if route == "policy":
        return "retrieve"
    if route in {"lookup", "refund", "retrieve"}:
        return route  # type: ignore[return-value]
    return "lookup"


def after_retrieve(state: DeskState) -> Literal["generate", "refuse"]:
    if state.get("passages"):
        return "generate"
    return "refuse"


def build_desk(model: Any = None, checkpointer: Any = None):
    """Compile the capstone desk. Defaults to InMemorySaver."""
    if checkpointer is None:
        checkpointer = InMemorySaver()

    def classify_node(state: DeskState, runtime: Any = None) -> dict[str, str]:
        return classify(state, runtime=runtime, model=model)

    def generate_node(state: DeskState, runtime: Any = None) -> dict[str, Any]:
        return generate(state, runtime=runtime, model=model)

    builder = StateGraph(DeskState)
    builder.add_node("classify", classify_node)
    builder.add_node("lookup", lookup_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)
    builder.add_node("refuse", refuse)
    builder.add_node("refund", refund_node)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        pick_route,
        {
            "lookup": "lookup",
            "refund": "refund",
            "retrieve": "retrieve",
        },
    )
    builder.add_conditional_edges(
        "retrieve",
        after_retrieve,
        {
            "generate": "generate",
            "refuse": "refuse",
        },
    )
    builder.add_edge("lookup", END)
    builder.add_edge("generate", END)
    builder.add_edge("refuse", END)
    builder.add_edge("refund", END)
    return builder.compile(checkpointer=checkpointer)


def run_ticket(
    ticket: str,
    *,
    model: Any = None,
    checkpointer: Any = None,
    thread_id: str = "desk",
) -> dict[str, Any]:
    graph = build_desk(model=model, checkpointer=checkpointer)
    cfg = {"configurable": {"thread_id": thread_id}}
    payload = {"ticket": ticket, "question": ticket}
    out = graph.invoke(payload, cfg)
    if not isinstance(out, dict):
        out = {"reply": str(out)}
    state = graph.get_state(cfg)
    interrupts = list(getattr(state, "interrupts", None) or [])
    if interrupts:
        payload_value = interrupts[0].value
        out["parked"] = True
        out["payload"] = payload_value
        if not out.get("reply"):
            out["reply"] = "Waiting for a reviewer to confirm the refund."
    else:
        out.setdefault("parked", False)
    return out
