"""Caps on a looping desk: recursion_limit, RemainingSteps, timeout, spend.

build_runaway plants a loop that never sets done. The world (the graph)
misbehaves here, not the model. The S16 bounce helper stays for run_with_cap(8).
"""

from __future__ import annotations

import asyncio
import operator
from typing import Annotated, Any, TypedDict

from langgraph.errors import GraphRecursionError, NodeError, NodeTimeoutError
from langgraph.graph import END, START, StateGraph
from langgraph.managed import RemainingSteps
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext

__all__ = [
    "build_bounce",
    "build_graceful",
    "build_runaway",
    "build_spend_capped",
    "build_timeout_demo",
    "run_with_cap",
]

PLAN_SYSTEM = (
    "You are the DataFlow planner. "
    "List the next single step for this ticket in one short sentence. "
    "Do not say the work is finished."
)

SUMMARIZE_SYSTEM = (
    "You write a one sentence DataFlow status line for this ticket. "
    "Do not invent an order that is not in the ticket."
)


class LoopState(TypedDict, total=False):
    n: int


class RunawayState(TypedDict, total=False):
    ticket: str
    done: bool
    plan: str
    steps: int
    reply: str


class GracefulState(TypedDict, total=False):
    ticket: str
    done: bool
    plan: str
    steps: int
    reply: str
    remaining_steps: RemainingSteps


class TimeoutState(TypedDict, total=False):
    ticket: str
    lookup: dict[str, Any]
    timeout_error: str
    timeout_detail: str


class SpendState(TypedDict, total=False):
    ticket: str
    spent_tokens: int
    budget_tokens: int
    call_count: int
    usage_source: str
    log: Annotated[list, operator.add]
    reply: str
    last_text: str


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


def _tokens_from_message(message: Any) -> tuple[int, str]:
    usage = getattr(message, "usage_metadata", None)
    if usage is None:
        meta = getattr(message, "response_metadata", None) or {}
        if isinstance(meta, dict):
            usage = meta.get("usage") or meta.get("token_usage")
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if total is not None:
            return int(total), "usage_metadata"
    if usage is not None:
        total = getattr(usage, "total_tokens", None)
        if total is not None:
            return int(total), "usage_metadata"
    return len(_content_text(message)), "characters"


def bounce(state: LoopState) -> dict:
    return {"n": int(state.get("n") or 0) + 1}


def build_bounce():
    """Planted cycle for the S16 lab. No model."""
    graph = StateGraph(LoopState)
    graph.add_node("bounce", bounce)
    graph.add_edge(START, "bounce")
    graph.add_edge("bounce", "bounce")
    return graph.compile()


def build_runaway(model=None):
    """Planner loops until done. Nothing ever sets done. That is the planted bug."""
    builder = StateGraph(RunawayState, context_schema=DeskContext)

    def planner(
        state: RunawayState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        chat = _resolve_chat(runtime, model)
        ticket = str(state.get("ticket") or "")
        message = chat.invoke(
            [
                {"role": "system", "content": PLAN_SYSTEM},
                {"role": "user", "content": ticket},
            ]
        )
        # Planted bug: nothing ever sets done. The graph loops until the cap.
        return {
            "plan": _content_text(message),
            "steps": int(state.get("steps") or 0) + 1,
            "done": False,
        }

    def route(state: RunawayState) -> str:
        if state.get("done"):
            return END
        return "planner"

    builder.add_node("planner", planner)
    builder.add_edge(START, "planner")
    builder.add_conditional_edges("planner", route)
    return builder.compile()


def build_graceful(model=None):
    """Same loop, but RemainingSteps lets the planner stop on purpose."""
    builder = StateGraph(GracefulState, context_schema=DeskContext)

    def planner(
        state: GracefulState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        remaining = int(state.get("remaining_steps") or 0)
        steps = int(state.get("steps") or 0) + 1
        if remaining <= 2:
            return {
                "done": True,
                "steps": steps,
                "reply": (
                    "The desk could not finish this request within its step budget."
                ),
            }
        chat = _resolve_chat(runtime, model)
        ticket = str(state.get("ticket") or "")
        message = chat.invoke(
            [
                {"role": "system", "content": PLAN_SYSTEM},
                {"role": "user", "content": ticket},
            ]
        )
        return {
            "plan": _content_text(message),
            "steps": steps,
            "done": False,
        }

    def route(state: GracefulState) -> str:
        if state.get("done"):
            return END
        return "planner"

    builder.add_node("planner", planner)
    builder.add_edge(START, "planner")
    builder.add_conditional_edges("planner", route)
    return builder.compile()


async def slow_lookup(state: TimeoutState) -> dict[str, Any]:
    """Sleep past the node timeout. Async so timeout= can cancel the wait."""
    # The world is slow here, not the model.
    await asyncio.sleep(3)
    return {"lookup": {"found": True, "reason": "carrier responded"}}


def timeout_error_handler(state: TimeoutState, error: NodeError) -> dict[str, Any]:
    inner = getattr(error, "error", error)
    return {
        "lookup": {
            "found": False,
            "reason": "lookup timed out after retries",
        },
        "timeout_error": type(inner).__name__,
        "timeout_detail": str(inner),
    }


def build_timeout_demo(model=None):
    """A 3 second lookup capped at timeout=1, two attempts, then a typed miss."""
    del model
    builder = StateGraph(TimeoutState)
    builder.add_node(
        "slow_lookup",
        slow_lookup,
        timeout=1,
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_interval=0.1,
            backoff_factor=2.0,
            retry_on=NodeTimeoutError,
        ),
        error_handler=timeout_error_handler,
    )
    builder.add_edge(START, "slow_lookup")
    builder.add_edge("slow_lookup", END)
    return builder.compile()


def build_spend_capped(budget_tokens: int = 600, model=None):
    """Loop a summarize node until spent_tokens passes the budget."""
    builder = StateGraph(SpendState, context_schema=DeskContext)

    def summarize(
        state: SpendState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        chat = _resolve_chat(runtime, model)
        ticket = str(state.get("ticket") or "")
        message = chat.invoke(
            [
                {"role": "system", "content": SUMMARIZE_SYSTEM},
                {"role": "user", "content": ticket},
            ]
        )
        n, source = _tokens_from_message(message)
        spent = int(state.get("spent_tokens") or 0) + n
        calls = int(state.get("call_count") or 0) + 1
        return {
            "spent_tokens": spent,
            "call_count": calls,
            "usage_source": source,
            "log": [n],
            "last_text": _content_text(message),
        }

    def route(state: SpendState) -> str:
        spent = int(state.get("spent_tokens") or 0)
        if spent > budget_tokens:
            return "stop"
        return "summarize"

    def stop(state: SpendState) -> dict[str, str]:
        n = int(state.get("spent_tokens") or 0)
        k = int(state.get("call_count") or 0)
        return {
            "reply": (
                f"Stopped: spent {n} tokens over a budget of {budget_tokens} "
                f"after {k} model calls."
            )
        }

    builder.add_node("summarize", summarize)
    builder.add_node("stop", stop)
    builder.add_edge(START, "summarize")
    builder.add_conditional_edges("summarize", route)
    builder.add_edge("stop", END)
    return builder.compile()


def run_with_cap(graph=None, ticket=None, recursion_limit: int = 8):
    """Run a graph with config recursion_limit.

    Legacy S16: run_with_cap(8) plants the bounce cycle and returns a dict.
    """
    if isinstance(graph, int) or graph is None:
        limit = graph if isinstance(graph, int) else recursion_limit
        bounce_graph = build_bounce()
        try:
            out = bounce_graph.invoke({"n": 0}, {"recursion_limit": limit})
            return {"stopped": False, "n": out.get("n"), "reason": "completed"}
        except GraphRecursionError as exc:
            return {
                "stopped": True,
                "reason": "recursion_limit",
                "detail": str(exc).split("\n")[0],
            }
    payload = {"ticket": ticket or "", "done": False}
    return graph.invoke(payload, {"recursion_limit": recursion_limit})
