"""Streamlit inbox: every parked DataFlow run, oldest first.

Each row carries its own thread id. Approve and Reject call desk_core
with that id. resolve_first is the planted miss that always resumes
the first row.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from langgraph.checkpoint.memory import InMemorySaver

from config import get_chat_model
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.ui.desk_core import approve, inbox_rows, reject, resolve_first

SAMPLE_ROWS = [
    {
        "thread_id": "night-T-3001",
        "age_seconds": 12.0,
        "payload": {
            "action": "refund",
            "order_id": "DF-1001",
            "amount": 49.0,
            "question": "Approve this refund of 49.0 on order DF-1001?",
        },
    },
    {
        "thread_id": "night-T-3009",
        "age_seconds": 4.0,
        "payload": {
            "action": "refund",
            "order_id": "DF-1009",
            "amount": 89.0,
            "question": "Approve this refund of 89.0 on order DF-1009?",
        },
    },
]


def _demo() -> str:
    return os.environ.get("DATAFLOW_UI_DEMO", "").strip().lower()


def _desk():
    if "saver" not in st.session_state:
        st.session_state.saver = InMemorySaver()
        st.session_state.graph = build_v4_hitl(
            checkpointer=st.session_state.saver,
            model=get_chat_model(),
        )
    return st.session_state.saver, st.session_state.graph


def render_row(row: dict, live: bool = False, graph=None) -> None:
    tid = str(row.get("thread_id") or "")
    st.markdown("**" + tid + "**")
    st.write("age_seconds", row.get("age_seconds"))
    st.write(row.get("payload"))
    left, right = st.columns(2)
    if live and graph is not None:
        if left.button("Approve", key="a-" + tid):
            st.write(approve(graph, tid))
            st.rerun()
        if right.button("Reject", key="r-" + tid):
            st.write(reject(graph, tid, "rejected from inbox"))
            st.rerun()
    else:
        left.button("Approve", key="a-" + tid)
        right.button("Reject", key="r-" + tid)


def main() -> None:
    st.set_page_config(page_title="DataFlow inbox", layout="centered")
    st.title("DataFlow inbox")
    demo = _demo()
    if demo == "inbox":
        st.info("demo: two parked rows, each with its own thread id")
        for row in SAMPLE_ROWS:
            render_row(row, live=False)
        return

    saver, graph = _desk()
    rows = inbox_rows(saver, graph)
    st.write("waiting", len(rows))
    planted = st.sidebar.checkbox("resolve first row only", value=False)
    if planted and rows:
        st.sidebar.caption("PLANTED: resumes the first row, not the one you meant")
        if st.sidebar.button("Planted resolve first"):
            st.write(resolve_first(graph, saver, "approve"))
            st.rerun()
    if not rows:
        st.write("No parked runs.")
        return
    for row in rows:
        render_row(row, live=True, graph=graph)


if __name__ == "__main__":
    main()
