"""Starter suite. No refuse test. Pytest stays green with no live model."""

from __future__ import annotations

from golden import load_rows
from retrieve import RETRIEVE_DESCRIPTION, retrieve
from tracer import LocalTraceHandler, traced_invoke

from app import health
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools import refund as refund_mod
from tests.fixtures.fake_model import FakeChatModel

REFUND_TICKET = "Please refund order DF-1001. The desk lamp is unused."


def test_retrieve_wired():
    assert retrieve.name == "retrieve"
    assert "customer" in (retrieve.description or RETRIEVE_DESCRIPTION).lower()


def test_golden_has_eight_rows():
    rows = load_rows()
    assert len(rows) == 8
    kinds = {str(row.get("kind") or "") for row in rows}
    assert "refuse" in kinds
    assert "lookup" in kinds
    assert "policy" in kinds


def test_health():
    body = health()
    assert body["ok"] is True
    assert body["service"] == "dataflow"


def test_refund_parks(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    cfg = {"configurable": {"thread_id": "starter-park"}}
    graph.invoke({"ticket": REFUND_TICKET}, cfg)
    state = graph.get_state(cfg)
    assert state.interrupts
    payload = state.interrupts[0].value
    assert payload["action"] == "refund"
    assert payload["order_id"] == "DF-1001"
    assert not path.exists()
    assert refund_mod.read_refunds() == []


def test_tracer_importable():
    assert LocalTraceHandler is not None
    assert traced_invoke is not None
