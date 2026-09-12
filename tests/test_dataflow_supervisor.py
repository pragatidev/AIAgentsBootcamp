"""6.9 DataFlow supervisor. Pytest stays green with no live model."""

import pytest
from langgraph.errors import InvalidUpdateError
from langgraph.types import Command

import dataflow.graphs.v7_supervisor as v7_mod
from dataflow.graphs.v7_supervisor import build_v7_supervisor
from dataflow.tools import refund as refund_mod
from tests.fixtures.fake_model import FakeChatModel

TICKET_3005 = "You billed me twice for order DF-1010. Please reverse the extra charge."


def _patch_refunds(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    monkeypatch.delenv("DATAFLOW_REFUNDS_PATH", raising=False)
    return path


def _thread(name: str) -> dict:
    return {"configurable": {"thread_id": name}}


def _team_model(**kwargs):
    structured = {
        "NextStep": [
            {"step": "billing", "why": "need the duplicate charge finding"},
            {"step": "writer", "why": "billing finding is enough to reply"},
        ],
        "BillingFinding": {
            "order_id": "DF-1010",
            "amount": 22.0,
            "refund_eligible": True,
            "reason": "billed twice",
        },
    }
    structured.update(kwargs.pop("structured", {}))
    return FakeChatModel(
        reply="We reversed the extra charge on DF-1010. Sorry for the duplicate bill.",
        structured=structured,
        **kwargs,
    )


def test_handoff_returns(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    graph = build_v7_supervisor(model=_team_model())
    cfg = _thread("test-15-handoff")
    graph.invoke({"ticket": TICKET_3005}, cfg)
    state = graph.get_state(cfg)
    assert state.interrupts
    notes = list((state.values or {}).get("notes") or [])
    sources = [row.get("source") for row in notes if isinstance(row, dict)]
    assert "billing" in sources
    finding = next(row for row in notes if row.get("source") == "billing")
    assert finding.get("order_id") == "DF-1010"
    done = graph.invoke(Command(resume="approve"), cfg)
    rows = refund_mod.read_refunds()
    assert len(rows) == 1
    assert rows[0]["order_id"] == "DF-1010"
    assert rows[0]["refunded"] is True
    assert done.get("reply")


def test_bad_return_caught(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    monkeypatch.setattr(v7_mod, "PLANT_BAD_RETURN", True)
    graph = build_v7_supervisor(model=_team_model())
    cfg = _thread("test-15-bad")
    out = graph.invoke({"ticket": TICKET_3005}, cfg)
    notes = list((out or {}).get("notes") or [])
    rejected = [row for row in notes if isinstance(row, dict) and row.get("rejected")]
    assert rejected
    assert "DF-9999" in str(rejected[0].get("reason"))
    assert str(out.get("reply") or "").startswith("Escalated")


def test_writer_is_the_only_writer(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    graph = build_v7_supervisor(
        model=_team_model(),
        parallel_writers=True,
    )
    with pytest.raises(InvalidUpdateError, match="one value"):
        graph.invoke({"ticket": TICKET_3005}, _thread("test-15-collide"))


def test_command_handoff_same_thread(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    graph = build_v7_supervisor(model=_team_model())
    cfg = _thread("test-15-history")
    graph.invoke({"ticket": TICKET_3005}, cfg)
    hist_parked = list(graph.get_state_history(cfg))
    assert len(hist_parked) > 2
    graph.invoke(Command(resume="approve"), cfg)
    hist_done = list(graph.get_state_history(cfg))
    assert len(hist_done) > len(hist_parked)
    notes = list((graph.get_state(cfg).values or {}).get("notes") or [])
    billing = [row for row in notes if row.get("source") == "billing"]
    assert billing
    assert billing[0].get("order_id") == "DF-1010"
    assert billing[0].get("amount") == 22.0


def test_max_handoffs_stops(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    model = _team_model(
        structured={
            "BillingFinding": {
                "order_id": "DF-1010",
                "amount": 22.0,
                "refund_eligible": False,
                "reason": "fixture, no refund so the cap can finish",
            }
        }
    )
    graph = build_v7_supervisor(
        model=model,
        plant_loop=True,
        max_handoffs=3,
    )
    out = graph.invoke({"ticket": TICKET_3005}, _thread("test-15-cap"))
    assert "handoff cap" in str(out.get("stop_reason") or "")


def test_usage_summed(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    model = _team_model(
        usage_metadata={
            "input_tokens": 6,
            "output_tokens": 4,
            "total_tokens": 10,
        }
    )
    graph = build_v7_supervisor(model=model)
    cfg = _thread("test-15-usage")
    graph.invoke({"ticket": TICKET_3005}, cfg)
    graph.invoke(Command(resume="approve"), cfg)
    values = graph.get_state(cfg).values or {}
    assert model.calls > 0
    assert values.get("usage_tokens") == 10 * model.calls
