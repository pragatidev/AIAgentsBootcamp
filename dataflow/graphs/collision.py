"""S10: two writes in one step. Without a reducer this raises InvalidUpdateError."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


class CollidingState(TypedDict):
    ticket: str
    log: str


class ReducedState(TypedDict):
    ticket: str
    log: Annotated[list[str], operator.add]


def write_a(state: dict) -> dict:
    return {"log": "orders looked up"}


def write_b(state: dict) -> dict:
    return {"log": "policy read"}


def write_a_list(state: dict) -> dict:
    return {"log": ["orders looked up"]}


def write_b_list(state: dict) -> dict:
    return {"log": ["policy read"]}


def build_collision():
    graph = StateGraph(CollidingState)
    graph.add_node("write_a", write_a)
    graph.add_node("write_b", write_b)
    graph.add_edge(START, "write_a")
    graph.add_edge(START, "write_b")
    graph.add_edge("write_a", END)
    graph.add_edge("write_b", END)
    return graph.compile()


def build_reduced():
    graph = StateGraph(ReducedState)
    graph.add_node("write_a", write_a_list)
    graph.add_node("write_b", write_b_list)
    graph.add_edge(START, "write_a")
    graph.add_edge(START, "write_b")
    graph.add_edge("write_a", END)
    graph.add_edge("write_b", END)
    return graph.compile()
