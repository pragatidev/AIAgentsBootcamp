"""DataFlow chat state: add_messages so every node appends."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext

AGENT_SYSTEM = (
    "You are the DataFlow support desk. "
    "Answer in one or two short sentences. "
    "Name any order id the customer mentioned."
)


class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]


def take_note(state: MessagesState) -> dict[str, list]:
    """Append a desk note. The reducer keeps the agent reply and this note."""
    messages = list(state.get("messages") or [])
    last_human = ""
    for message in reversed(messages):
        if getattr(message, "type", "") == "human":
            last_human = _content_text(message)
            break
    snippet = last_human.replace("\n", " ").strip()
    if len(snippet) > 80:
        snippet = snippet[:80]
    note = f"desk note: recorded the ticket ({snippet})"
    return {"messages": [AIMessage(content=note, name="note")]}


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


def build_messages_graph(*, model: Any = None):
    builder = StateGraph(MessagesState, context_schema=DeskContext)

    def agent(
        state: MessagesState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, list]:
        chat = model
        if chat is None and runtime is not None:
            ctx = getattr(runtime, "context", None)
            chat = getattr(ctx, "model", None) if ctx is not None else None
        if chat is None:
            chat = get_chat_model()
        history = list(state.get("messages") or [])
        result = chat.invoke([SystemMessage(content=AGENT_SYSTEM), *history])
        return {"messages": [result]}

    builder.add_node("agent", agent)
    builder.add_node("take_note", take_note)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", "take_note")
    builder.add_edge("take_note", END)
    return builder.compile()
