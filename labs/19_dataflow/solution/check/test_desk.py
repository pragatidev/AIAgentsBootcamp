"""Filled desk. Fixture model. Includes the refuse test the starter omitted."""

from __future__ import annotations

from graph import run_ticket
from tests.fixtures.fake_model import FakeChatModel

COFFEE = "Do you sell coffee beans in the DataFlow shop?"
LOOKUP = "Where is order DF-1001?"
REFUND = "Please refund order DF-1001. The desk lamp is unused."


def test_lookup_with_fixture():
    out = run_ticket(LOOKUP, model=FakeChatModel(route="lookup"), thread_id="sol-lookup")
    assert out.get("parked") is False
    reply = str(out.get("reply") or "")
    assert "looked up" in reply or "DF-1001" in reply


def test_refund_parks_with_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "refunds.jsonl"))
    out = run_ticket(REFUND, model=FakeChatModel(route="refund"), thread_id="sol-park")
    assert out.get("parked") is True
    payload = out.get("payload") or {}
    assert payload.get("action") == "refund"
    assert payload.get("order_id") == "DF-1001"


def test_refuse_on_empty(monkeypatch):
    monkeypatch.setattr(
        "dataflow.graphs.rag_graph.retrieve_passages",
        lambda *args, **kwargs: [],
    )
    out = run_ticket(COFFEE, model=FakeChatModel(route="policy"), thread_id="sol-refuse")
    reply = str(out.get("reply") or out.get("answer") or "")
    assert "I do not have that in the knowledge base" in reply
    assert out.get("parked") is False
