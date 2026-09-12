"""6.8 caps: recursion limit, RemainingSteps, timeout, spend. No live model."""

from __future__ import annotations

import asyncio

import pytest
from langgraph.errors import GraphRecursionError

from dataflow.graphs.runaway import (
    build_graceful,
    build_runaway,
    build_spend_capped,
    build_timeout_demo,
    run_with_cap,
)
from tests.fixtures.fake_model import FakeChatModel

TICKET = "Where is order DF-1002? Tracking still says in transit."


def test_recursion_error_named():
    graph = build_runaway(model=FakeChatModel(reply="Look up the order next."))
    with pytest.raises(GraphRecursionError):
        run_with_cap(graph, TICKET, recursion_limit=8)


def test_remaining_steps_graceful():
    graph = build_graceful(model=FakeChatModel(reply="Look up the order next."))
    out = graph.invoke(
        {"ticket": TICKET, "done": False},
        {"recursion_limit": 8},
    )
    assert "could not finish" in (out.get("reply") or "")


def test_timeout_fires():
    out = asyncio.run(build_timeout_demo().ainvoke({"ticket": TICKET}))
    lookup = (out or {}).get("lookup") or {}
    assert lookup.get("found") is False
    assert out.get("timeout_error") == "NodeTimeoutError"


def test_cap_stops_with_reason():
    model = FakeChatModel(
        reply="status line",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 300,
            "total_tokens": 400,
        },
    )
    out = build_spend_capped(budget_tokens=600, model=model).invoke({"ticket": TICKET})
    reply = out.get("reply") or ""
    assert reply.startswith("Stopped:")
