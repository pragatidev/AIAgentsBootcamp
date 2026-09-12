"""DataFlow v3: the desk with a checkpointer and an optional store.

The thread is this conversation. The store is facts across conversations.
Compile takes a checkpointer. Nodes reach the store through the runtime.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext, classify
from dataflow.graphs.v2_route import (
    escalate_desk,
    orders_desk,
    pick_route,
    policy_desk,
)

__all__ = [
    "DeskContext",
    "MemoryState",
    "PREFERENCE_KEY",
    "build_v3_memory",
    "preference_namespace",
    "read_preference",
    "remember_preference",
]

PREFERENCE_KEY = "preferences"

SPEAK_SYSTEM = (
    "You are the DataFlow support desk continuing this ticket thread. "
    "Answer in one or two short sentences. "
    "When the desk notes include an earlier request, mention it in the reply. "
    "If the desk notes include a contact preference, say it plainly."
)


class MemoryState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    ticket: str
    route: str
    order: dict[str, Any]
    policy: dict[str, Any]
    escalation: dict[str, Any]
    reply: str
    preference: dict[str, Any] | None
    turns: int
    last_ticket: str


def preference_namespace(customer_id: str) -> tuple[str, str]:
    return ("customers", customer_id)


def remember_preference(
    store: BaseStore, customer_id: str, key: str, value: str
) -> None:
    item = store.get(preference_namespace(customer_id), PREFERENCE_KEY)
    current = dict(item.value) if item is not None else {}
    current[key] = value
    store.put(preference_namespace(customer_id), PREFERENCE_KEY, current)


def read_preference(store: BaseStore, customer_id: str, key: str) -> str | None:
    item = store.get(preference_namespace(customer_id), PREFERENCE_KEY)
    if item is None:
        return None
    found = item.value.get(key)
    return str(found) if found is not None else None


def _content_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)
    return str(content or "")


def _customer_id(runtime: Runtime[DeskContext] | None) -> str:
    if runtime is None:
        return "anon"
    ctx = getattr(runtime, "context", None)
    if ctx is None:
        return "anon"
    return str(getattr(ctx, "customer_id", None) or "anon")


def _resolve_model(runtime: Runtime[DeskContext] | None, model: Any) -> Any:
    chat = model
    if chat is None and runtime is not None:
        ctx = getattr(runtime, "context", None)
        chat = getattr(ctx, "model", None) if ctx is not None else None
    if chat is None:
        chat = get_chat_model()
    return chat


def _last_human(messages: list) -> str:
    for message in reversed(messages):
        if getattr(message, "type", "") == "human":
            return _content_text(message)
    return ""


def _preference_from_text(text: str) -> dict[str, Any] | None:
    lower = text.lower()
    if not lower:
        return None
    wants_email = (
        "always email" in lower
        or "email me" in lower
        or ("prefer" in lower and "email" in lower)
    )
    never_call = "never call" in lower
    if wants_email or ("email" in lower and never_call):
        return {"channel": "email", "raw": text.strip()}
    if "always call" in lower or ("prefer" in lower and "call" in lower):
        return {"channel": "call", "raw": text.strip()}
    return None


def ingest(state: MemoryState) -> dict[str, Any]:
    """Seed ticket and messages, then count this invoke as one turn."""
    ticket = str(state.get("ticket") or "")
    messages = list(state.get("messages") or [])
    last_human = _last_human(messages)
    if not ticket:
        ticket = last_human
    updates: dict[str, Any] = {
        "ticket": ticket,
        "last_ticket": ticket,
        "turns": int(state.get("turns") or 0) + 1,
    }
    if ticket and ticket != last_human:
        updates["messages"] = [HumanMessage(content=ticket)]
    return updates


def read_pref(
    state: MemoryState,
    runtime: Runtime[DeskContext] | None = None,
) -> dict[str, Any]:
    """Read the customer's preferences from the store when a store is present."""
    if runtime is None or runtime.store is None:
        return {}
    customer_id = _customer_id(runtime)
    item = runtime.store.get(preference_namespace(customer_id), PREFERENCE_KEY)
    if item is None:
        return {"preference": None}
    return {"preference": dict(item.value)}


def write_pref(
    state: MemoryState,
    runtime: Runtime[DeskContext] | None = None,
) -> dict[str, Any]:
    """Write a preference when the customer states one."""
    if runtime is None or runtime.store is None:
        return {}
    ticket = str(state.get("ticket") or "")
    pref = _preference_from_text(ticket)
    if pref is None:
        return {}
    customer_id = _customer_id(runtime)
    runtime.store.put(preference_namespace(customer_id), PREFERENCE_KEY, pref)
    return {"preference": pref}


def build_v3_memory(checkpointer=None, store=None, model=None):
    """Compile the desk. Defaults to InMemorySaver when checkpointer is None."""
    if checkpointer is None:
        checkpointer = InMemorySaver()

    builder = StateGraph(MemoryState, context_schema=DeskContext)

    def classify_node(
        state: MemoryState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return classify(state, runtime=runtime, model=model)

    def speak(
        state: MemoryState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        chat = _resolve_model(runtime, model)
        history = list(state.get("messages") or [])
        desk_reply = str(state.get("reply") or "")
        pref = state.get("preference") or {}
        notes: list[str] = []
        if desk_reply:
            notes.append(f"Lookup: {desk_reply}")
        humans = [
            _content_text(message)
            for message in history
            if getattr(message, "type", "") == "human"
        ]
        if len(humans) >= 2:
            earlier = humans[0].replace("\n", " ").strip()
            if len(earlier) > 160:
                earlier = earlier[:160]
            notes.append(
                "Earlier in this thread the customer said: "
                + earlier
                + " Name that earlier request when you answer the follow up."
            )
        channel = pref.get("channel") if isinstance(pref, dict) else None
        if channel:
            notes.append(f"Saved preference: contact by {channel}.")
        extra = (" Desk notes: " + " ".join(notes)) if notes else ""
        result = chat.invoke(
            [SystemMessage(content=SPEAK_SYSTEM + extra), *history]
        )
        text = _content_text(result)
        if channel == "email" and "email" not in text.lower():
            text = f"{text} We will email you, never call."
        return {"messages": [AIMessage(content=text)], "reply": text}

    builder.add_node("ingest", ingest)
    builder.add_node("read_pref", read_pref)
    builder.add_node("classify", classify_node)
    builder.add_node("orders_desk", orders_desk)
    builder.add_node("policy_desk", policy_desk)
    builder.add_node("escalate_desk", escalate_desk)
    builder.add_node("write_pref", write_pref)
    builder.add_node("speak", speak)
    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "read_pref")
    builder.add_edge("read_pref", "classify")
    builder.add_conditional_edges(
        "classify",
        pick_route,
        {
            "orders": "orders_desk",
            "policy": "policy_desk",
            "escalate": "escalate_desk",
        },
    )
    builder.add_edge("orders_desk", "write_pref")
    builder.add_edge("policy_desk", "write_pref")
    builder.add_edge("escalate_desk", "write_pref")
    builder.add_edge("write_pref", "speak")
    builder.add_edge("speak", END)
    return builder.compile(checkpointer=checkpointer, store=store)
