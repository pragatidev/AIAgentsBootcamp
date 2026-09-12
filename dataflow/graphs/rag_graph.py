"""Agentic RAG graph: route, retrieve, grade, rewrite, generate, refuse.

Every node that decides calls the chat model from config. No keyword
stand-in for a model decision.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from config import get_chat_model
from dataflow.graphs.crag import MAX_REWRITES, after_grade, widen
from dataflow.graphs.v1_triage import DeskContext
from dataflow.rag.faiss_index import search
from dataflow.tools.orders import lookup_order_from_ticket
from dataflow.tools.retrieve import get_index, retrieve_passages

ROUTE_SYSTEM = (
    "You route DataFlow support tickets. Pick exactly one route. "
    "retrieve: the customer asks about a policy, guide, return window, "
    "shipping, pricing, or how something works, and does not name an order id. "
    "lookup: the ticket names an order id like DF-1001, or asks where an order is. "
    "answer: thanks, chitchat, or a question that needs no search and no lookup."
)

GRADE_SYSTEM = (
    "You grade a retrieved passage for a customer support question. "
    "The customer is a buyer, not an employee. "
    "keep: the passage answers the customer's question from a customer-facing "
    "policy or guide. "
    "drop: the passage is unrelated or too thin to use. "
    "wrong: the passage is about employees, HR, internal equipment, or a "
    "different topic than the customer asked. "
    "Return one label and a one sentence reason."
)

REWRITE_SYSTEM = (
    "Rephrase the customer's question using the words a DataFlow policy "
    "document would use. Keep the same meaning. Return only the rewritten question."
)

GENERATE_SYSTEM = (
    "Answer the customer using only the kept passages below. "
    "If the passages do not contain the answer, say you do not have it. "
    "Do not use employee handbook rules for a customer. "
    "Do not invent a policy."
)

ANSWER_SYSTEM = (
    "You are the DataFlow support desk. Reply in one or two short sentences. "
    "Do not look up a policy. Do not invent one."
)

REFUSE_TEMPLATE = (
    "I do not have that in the knowledge base. I understood the question as: {q}. "
    "You can rephrase it or ask to speak to a person."
)


class RagState(TypedDict, total=False):
    question: str
    route: str
    passages: list[dict[str, Any]]
    graded: list[dict[str, Any]]
    grades: list[dict[str, Any]]
    rewrites: int
    rewritten_question: str
    answer: str
    sources: list[dict[str, Any]]
    reply: str
    order: dict[str, Any]


class Route(BaseModel):
    route: Literal["retrieve", "lookup", "answer"] = Field(
        description="retrieve a policy, lookup an order, or answer chitchat"
    )


class Grade(BaseModel):
    label: Literal["keep", "drop", "wrong"] = Field(
        description="keep the passage, drop it as noise, or mark it wrong"
    )
    reason: str = Field(description="One sentence why")


def _chat(model: Any, runtime: Runtime[DeskContext] | None) -> Any:
    chat = model
    if chat is None and runtime is not None:
        ctx = getattr(runtime, "context", None)
        chat = getattr(ctx, "model", None) if ctx is not None else None
    if chat is None:
        chat = get_chat_model()
    return chat


def _content(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "\n".join(part for part in parts if part).strip()
    return str(content or "").strip()


def route(
    state: RagState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, str]:
    chat = _chat(model, runtime)
    structured = chat.with_structured_output(Route)
    question = state.get("question") or ""
    decision = structured.invoke(
        [
            {"role": "system", "content": ROUTE_SYSTEM},
            {"role": "user", "content": question},
        ]
    )
    if hasattr(decision, "route"):
        chosen = decision.route
    else:
        chosen = decision["route"]
    return {"route": str(chosen)}


def retrieve_node(
    state: RagState,
    *,
    scope: str = "customer",
) -> dict[str, Any]:
    question = state.get("rewritten_question") or state.get("question") or ""
    if scope == "all":
        hits = search(get_index(), question, k=3, folder=None)
    else:
        hits = retrieve_passages(question, k=3, folder=None)
    return {"passages": hits}


def grade(
    state: RagState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, Any]:
    chat = _chat(model, runtime)
    structured = chat.with_structured_output(Grade)
    question = state.get("rewritten_question") or state.get("question") or ""
    passages = list(state.get("passages") or [])
    grades: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for passage in passages:
        source = str(passage.get("source") or "")
        text = str(passage.get("text") or "")
        decision = structured.invoke(
            [
                {"role": "system", "content": GRADE_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n"
                        f"Source: {source}\n"
                        f"Passage:\n{text}"
                    ),
                },
            ]
        )
        if hasattr(decision, "label"):
            label = str(decision.label)
            reason = str(decision.reason)
        else:
            label = str(decision.get("label") or "drop")
            reason = str(decision.get("reason") or "")
        row = {
            "source": source,
            "label": label,
            "reason": reason,
            "text": text,
        }
        grades.append(row)
        if label == "keep":
            kept.append(passage)
    return {"grades": grades, "graded": kept}


def rewrite(
    state: RagState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, Any]:
    chat = _chat(model, runtime)
    question = state.get("rewritten_question") or state.get("question") or ""
    result = chat.invoke(
        [
            SystemMessage(content=REWRITE_SYSTEM),
            HumanMessage(content=question),
        ]
    )
    rewritten = _content(result) or question
    spent = int(state.get("rewrites") or 0) + 1
    return {"rewritten_question": rewritten, "rewrites": spent}


def generate(
    state: RagState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
    strip_sources: bool = False,
) -> dict[str, Any]:
    chat = _chat(model, runtime)
    question = state.get("rewritten_question") or state.get("question") or ""
    kept = list(state.get("graded") or [])
    blob = "\n\n".join(
        f"Source: {row.get('source')}\n{row.get('text')}" for row in kept
    )
    result = chat.invoke(
        [
            SystemMessage(content=GENERATE_SYSTEM),
            HumanMessage(
                content=f"Question: {question}\n\nPassages:\n{blob or '(none)'}"
            ),
        ]
    )
    text = _content(result)
    sources: list[dict[str, Any]] = []
    if not strip_sources:
        for row in kept:
            sources.append(
                {
                    "source": row.get("source"),
                    "heading_path": row.get("heading_path"),
                    "row": row.get("row"),
                    "h2": row.get("h2"),
                    "h3": row.get("h3"),
                }
            )
    return {"answer": text, "reply": text, "sources": sources}


def refuse(state: RagState) -> dict[str, Any]:
    question = state.get("rewritten_question") or state.get("question") or ""
    text = REFUSE_TEMPLATE.format(q=question)
    return {"reply": text, "answer": text, "sources": []}


def lookup_node(state: RagState) -> dict[str, Any]:
    question = state.get("question") or ""
    order = lookup_order_from_ticket(question)
    if order.get("found"):
        text = (
            f"Order {order['order_id']} is {order['status']}. "
            f"Item: {order['item']}."
        )
    else:
        reason = order.get("reason", "no order")
        text = f"I could not find that order ({reason})."
    return {
        "order": order,
        "reply": text,
        "answer": text,
        "sources": [],
    }


def answer_node(
    state: RagState,
    runtime: Runtime[DeskContext] | None = None,
    *,
    model: Any = None,
) -> dict[str, Any]:
    chat = _chat(model, runtime)
    question = state.get("question") or ""
    result = chat.invoke(
        [
            SystemMessage(content=ANSWER_SYSTEM),
            HumanMessage(content=question),
        ]
    )
    text = _content(result)
    return {"reply": text, "answer": text, "sources": []}


def pick_route(state: RagState) -> Literal["retrieve", "lookup", "answer"]:
    chosen = str(state.get("route") or "answer")
    if chosen in {"retrieve", "lookup", "answer"}:
        return chosen  # type: ignore[return-value]
    return "answer"


def build_rag_graph(
    *,
    model: Any = None,
    checkpointer: Any = None,
    grade_enabled: bool = True,
    max_rewrites: int = MAX_REWRITES,
    web_search_allowed: bool = False,
    strip_sources: bool = False,
    force_generate_on_empty: bool = False,
    scope: str = "customer",
    cite_node: Any = None,
):
    builder = StateGraph(RagState, context_schema=DeskContext)

    def route_node(
        state: RagState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return route(state, runtime=runtime, model=model)

    def retrieve_bound(state: RagState) -> dict[str, Any]:
        return retrieve_node(state, scope=scope)

    def grade_node(
        state: RagState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return grade(state, runtime=runtime, model=model)

    def rewrite_node(
        state: RagState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return rewrite(state, runtime=runtime, model=model)

    def generate_node(
        state: RagState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return generate(
            state,
            runtime=runtime,
            model=model,
            strip_sources=strip_sources,
        )

    def answer_bound(
        state: RagState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return answer_node(state, runtime=runtime, model=model)

    def widen_node(state: RagState) -> dict[str, Any]:
        return widen(state, web_search_allowed=web_search_allowed)

    def pick_after_grade(state: RagState) -> str:
        if force_generate_on_empty:
            kept = [
                row
                for row in (state.get("grades") or [])
                if str(row.get("label") or "") == "keep"
            ]
            if not kept and not (state.get("graded") or []):
                return "generate"
        return after_grade(
            dict(state),
            max_rewrites=max_rewrites,
            web_search_allowed=web_search_allowed,
        )

    builder.add_node("route", route_node)
    builder.add_node("retrieve", retrieve_bound)
    builder.add_node("grade", grade_node)
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("generate", generate_node)
    builder.add_node("refuse", refuse)
    builder.add_node("lookup", lookup_node)
    builder.add_node("answer", answer_bound)
    builder.add_node("widen", widen_node)

    builder.add_edge(START, "route")
    builder.add_conditional_edges(
        "route",
        pick_route,
        {
            "retrieve": "retrieve",
            "lookup": "lookup",
            "answer": "answer",
        },
    )
    if grade_enabled:
        builder.add_edge("retrieve", "grade")
        builder.add_conditional_edges(
            "grade",
            pick_after_grade,
            {
                "generate": "generate",
                "rewrite": "rewrite",
                "refuse": "refuse",
                "widen": "widen",
            },
        )
        builder.add_edge("rewrite", "retrieve")
        builder.add_edge("widen", "grade")
    else:
        builder.add_edge("retrieve", "generate")

    if cite_node is not None:
        builder.add_node("cite", cite_node)
        builder.add_edge("generate", "cite")
        builder.add_edge("answer", "cite")
        builder.add_edge("cite", END)
        builder.add_edge("lookup", END)
        builder.add_edge("refuse", END)
    else:
        builder.add_edge("generate", END)
        builder.add_edge("answer", END)
        builder.add_edge("lookup", END)
        builder.add_edge("refuse", END)

    return builder.compile(checkpointer=checkpointer)
