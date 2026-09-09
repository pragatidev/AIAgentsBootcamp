"""S11: checkpointer resumes a thread. Store holds a fact across threads."""

from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore


class MemoryState(TypedDict, total=False):
    ticket: str
    turns: int
    last_ticket: str


def bump(state: MemoryState) -> dict:
    n = int(state.get("turns") or 0) + 1
    return {"turns": n, "last_ticket": state.get("ticket", "")}


def build_v3_memory(checkpointer=None):
    graph = StateGraph(MemoryState)
    graph.add_node("bump", bump)
    graph.add_edge(START, "bump")
    graph.add_edge("bump", END)
    return graph.compile(checkpointer=checkpointer or MemorySaver())


def remember_preference(store: InMemoryStore, customer_id: str, key: str, value: str) -> None:
    store.put(("prefs", customer_id), key, {"value": value})


def read_preference(store: InMemoryStore, customer_id: str, key: str) -> str | None:
    item = store.get(("prefs", customer_id), key)
    if item is None:
        return None
    return item.value.get("value")
