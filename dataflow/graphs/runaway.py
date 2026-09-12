"""S16: plant a cycle. Recursion limit is the stop. Log the reason."""

from __future__ import annotations

from typing import TypedDict

from langgraph.errors import GraphRecursionError
from langgraph.graph import START, StateGraph


class LoopState(TypedDict, total=False):
    n: int


def bounce(state: LoopState) -> dict:
    return {"n": int(state.get("n") or 0) + 1}


def build_runaway():
    graph = StateGraph(LoopState)
    graph.add_node("bounce", bounce)
    graph.add_edge(START, "bounce")
    graph.add_edge("bounce", "bounce")
    return graph.compile()


def run_with_cap(limit: int = 8) -> dict:
    graph = build_runaway()
    try:
        out = graph.invoke({"n": 0}, {"recursion_limit": limit})
        return {"stopped": False, "n": out.get("n"), "reason": "completed"}
    except GraphRecursionError as exc:
        return {"stopped": True, "reason": "recursion_limit", "detail": str(exc).split("\n")[0]}
