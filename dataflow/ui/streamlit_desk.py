"""Streamlit chat page for the DataFlow desk.

Sibling of dataflow/serve/app.py (the thin FastAPI page). Gradio is named
in the lectures and is not used here.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from langgraph.checkpoint.memory import InMemorySaver

from config import get_chat_model
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.ui.desk_core import (
    approve,
    edit,
    events_as_json,
    reject,
    run_blocking,
    stream_tokens,
)

SAMPLE_TOOL = {
    "name": "issue_refund",
    "args": {"order_id": "DF-1001", "amount": 49.0, "reason": "unused lamp"},
}
SAMPLE_PARK = {
    "action": "refund",
    "order_id": "DF-1001",
    "amount": 49.0,
    "policy": "Customers may return unused items within 30 days of delivery.",
    "question": "Approve this refund of 49.0 on order DF-1001?",
}


def _demo() -> str:
    return os.environ.get("DATAFLOW_UI_DEMO", "").strip().lower()


def _graph_and_thread():
    if "saver" not in st.session_state:
        st.session_state.saver = InMemorySaver()
        st.session_state.thread_id = "desk-" + uuid.uuid4().hex[:8]
        st.session_state.graph = build_v4_hitl(
            checkpointer=st.session_state.saver,
            model=get_chat_model(),
        )
        st.session_state.events = []
        st.session_state.park = None
        st.session_state.result = None
    return st.session_state.graph, st.session_state.thread_id


def render_tool_card(payload: dict) -> None:
    name = str(payload.get("name") or "tool")
    args = payload.get("args") or {}
    st.markdown("**Tool: " + name + "**")
    st.write(args)


def render_park_card(payload: dict) -> None:
    st.markdown("**Waiting: refund**")
    st.write("The run is parked. A person has to answer before any write.")
    for key in ("action", "order_id", "amount", "policy", "question", "ticket"):
        if key in payload:
            st.write(key, payload.get(key))


def render_events(events: list, raw: bool) -> None:
    if raw:
        st.code(events_as_json(events), language="json")
        st.caption("raw JSON. A park in this dump looks like a crash.")
        return
    text = ""
    nodes: list[str] = []
    park = None
    for kind, payload in events:
        if kind == "token":
            text += str(payload)
        elif kind == "node":
            nodes.append(str(payload))
        elif kind == "tool_call":
            render_tool_card(payload if isinstance(payload, dict) else {"name": str(payload)})
        elif kind == "interrupt":
            park = payload if isinstance(payload, dict) else {"value": payload}
            render_park_card(park)
    if text:
        st.chat_message("assistant").write(text)
    if nodes:
        st.caption("nodes: " + " | ".join(nodes))
    if park is not None:
        st.session_state.park = park


def render_approval_buttons(graph, thread_id: str) -> None:
    if st.session_state.get("park") is None:
        return
    st.subheader("Approval")
    left, mid, right = st.columns(3)
    with left:
        if st.button("Approve"):
            st.session_state.result = approve(graph, thread_id)
            st.session_state.park = None
    with mid:
        reason = st.text_input("reject reason", value="not unused")
        if st.button("Reject"):
            st.session_state.result = reject(graph, thread_id, reason)
            st.session_state.park = None
    with right:
        amount = st.number_input("edit amount", value=20.0)
        edit_reason = st.text_input("edit reason", value="partial refund")
        if st.button("Edit"):
            st.session_state.result = edit(
                graph,
                thread_id,
                {"amount": float(amount), "reason": edit_reason},
            )
            st.session_state.park = None
    if st.session_state.get("result"):
        st.write(st.session_state.result)


def main() -> None:
    st.set_page_config(page_title="DataFlow desk", layout="centered")
    st.title("DataFlow desk")
    demo = _demo()
    graph, thread_id = _graph_and_thread()
    st.sidebar.write("thread id")
    st.sidebar.code(thread_id)
    blocking = st.sidebar.checkbox("blocking", value=False)
    raw = st.sidebar.checkbox("raw", value=False)

    if demo == "cards":
        st.info("demo: tool card and park card")
        render_tool_card(SAMPLE_TOOL)
        render_park_card(SAMPLE_PARK)
        return

    if demo == "approval":
        st.info("demo: park card with Approve, Reject, Edit")
        render_tool_card(SAMPLE_TOOL)
        render_park_card(SAMPLE_PARK)
        st.session_state.park = SAMPLE_PARK
        st.subheader("Approval")
        c1, c2, c3 = st.columns(3)
        c1.button("Approve")
        c2.text_input("reject reason", value="not unused")
        c2.button("Reject")
        c3.number_input("edit amount", value=20.0)
        c3.text_input("edit reason", value="partial refund")
        c3.button("Edit")
        return

    ticket = st.text_input("ticket", placeholder="Where is order DF-1002?")
    send = st.button("Send")
    if send and ticket:
        st.session_state.park = None
        st.session_state.result = None
        events: list = []
        bubble = st.empty()
        nodes_box = st.empty()
        cards = st.container()
        text = ""
        nodes: list[str] = []
        source = run_blocking if blocking else stream_tokens
        if blocking:
            with st.spinner("invoke is blocking. The page stays blank until the end."):
                events = list(source(graph, ticket, thread_id))
            render_events(events, raw=raw)
        else:
            for kind, payload in source(graph, ticket, thread_id):
                events.append((kind, payload))
                if raw:
                    continue
                if kind == "token":
                    text += str(payload)
                    bubble.markdown(text)
                elif kind == "node":
                    nodes.append(str(payload))
                    nodes_box.caption("nodes: " + " | ".join(nodes))
                elif kind == "tool_call":
                    with cards:
                        render_tool_card(
                            payload if isinstance(payload, dict) else {"name": str(payload)}
                        )
                elif kind == "interrupt":
                    park = payload if isinstance(payload, dict) else {"value": payload}
                    st.session_state.park = park
                    with cards:
                        render_park_card(park)
            if raw:
                render_events(events, raw=True)
        st.session_state.events = events

    if st.session_state.get("events") and not send:
        render_events(st.session_state.events, raw=raw)

    render_approval_buttons(graph, thread_id)


if __name__ == "__main__":
    main()
