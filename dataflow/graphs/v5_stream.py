"""DataFlow v5: the v3 desk plus a custom stream lane.

Same nodes as v3. Speak emits progress with get_stream_writer and
iterates chat.stream so messages mode gets real token chunks.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from dataflow.graphs.v1_triage import DeskContext, classify
from dataflow.graphs.v2_route import (
    escalate_desk,
    orders_desk,
    pick_route,
    policy_desk,
)
from dataflow.graphs.v3_memory import (
    SPEAK_SYSTEM,
    MemoryState,
    _content_text,
    _resolve_model,
    ingest,
    read_pref,
    write_pref,
)

__all__ = [
    "DeskContext",
    "MemoryState",
    "build_v5_stream",
]


def _emit_progress(text: str) -> None:
    """Push a custom progress dict. No-op outside a run or without custom mode."""
    try:
        writer = get_stream_writer()
    except Exception:
        return
    try:
        writer({"progress": text})
    except Exception:
        return


def _speak_text(chat: Any, prompt: list) -> str:
    """Join chat.stream chunks when the model can stream, else invoke once."""
    streamer = getattr(chat, "stream", None)
    if callable(streamer):
        pieces: list[str] = []
        for chunk in streamer(prompt):
            pieces.append(_content_text(chunk))
        return "".join(pieces)
    result = chat.invoke(prompt)
    return _content_text(result)


def build_v5_stream(checkpointer=None, store=None, model=None):
    """Compile the v3 desk with streaming speak. Defaults to InMemorySaver."""
    if checkpointer is None:
        checkpointer = InMemorySaver()

    builder = StateGraph(MemoryState, context_schema=DeskContext)

    def classify_node(
        state: MemoryState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, str]:
        return classify(state, runtime=runtime, model=model)

    def write_pref_node(
        state: MemoryState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, Any]:
        return write_pref(state, runtime=runtime, model=model)

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
        prompt = [SystemMessage(content=SPEAK_SYSTEM + extra), *history]
        _emit_progress("calling the model")
        text = _speak_text(chat, prompt)
        _emit_progress("model finished")
        return {"messages": [AIMessage(content=text)], "reply": text}

    builder.add_node("ingest", ingest)
    builder.add_node("read_pref", read_pref)
    builder.add_node("classify", classify_node)
    builder.add_node("orders_desk", orders_desk)
    builder.add_node("policy_desk", policy_desk)
    builder.add_node("escalate_desk", escalate_desk)
    builder.add_node("write_pref", write_pref_node)
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
