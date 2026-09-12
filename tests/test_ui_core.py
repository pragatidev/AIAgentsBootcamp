"""14.1 DataFlow Streamlit core. Pytest stays green with no live model."""

from __future__ import annotations

import inspect

from langgraph.checkpoint.memory import InMemorySaver

from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools import refund as refund_mod
from dataflow.ui.desk_core import run_blocking, stream_tokens
from tests.fixtures.fake_model import FakeChatModel

REFUND_TICKET = "Please refund order DF-1001, the lamp is unused"
LOOKUP_TICKET = "Where is order DF-1002?"


def _patch_refunds(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    return path


def test_stream_tokens_refund_kinds(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(
        checkpointer=InMemorySaver(),
        model=FakeChatModel(route="refund"),
    )
    kinds = set()
    payloads = []
    for kind, payload in stream_tokens(graph, REFUND_TICKET, "ui-refund"):
        kinds.add(kind)
        payloads.append((kind, payload))
    assert "token" in kinds
    assert "node" in kinds
    assert "tool_call" in kinds
    assert "interrupt" in kinds
    interrupt = next(p for k, p in payloads if k == "interrupt")
    assert isinstance(interrupt, dict)
    assert interrupt.get("action") == "refund"
    assert interrupt.get("order_id") == "DF-1001"
    tool = next(p for k, p in payloads if k == "tool_call")
    assert tool.get("name")
    assert "args" in tool


def test_run_blocking_returns_only_at_the_end(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(
        checkpointer=InMemorySaver(),
        model=FakeChatModel(route="lookup"),
    )
    gen = run_blocking(graph, LOOKUP_TICKET, "ui-block")
    assert inspect.getgeneratorstate(gen) == inspect.GEN_CREATED
    events = list(gen)
    assert inspect.getgeneratorstate(gen) == inspect.GEN_CLOSED
    assert events
    # invoke finishes before the first yield, so a UI sees nothing
    # until completion.
    kinds = {kind for kind, _payload in events}
    assert "node" in kinds or "token" in kinds
