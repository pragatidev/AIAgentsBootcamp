"""6.5 DataFlow interrupt. Pytest stays green with no live model."""

from dataflow.graphs.v4_hitl import build_v4_hitl, resume_with
from dataflow.tools import refund as refund_mod
from tests.fixtures.fake_model import FakeChatModel

REFUND_TICKET = "Please refund order DF-1001. The desk lamp is unused."
LOOKUP_TICKET = "Where is order DF-1001?"


def _patch_refunds(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    monkeypatch.delenv("DATAFLOW_REFUNDS_PATH", raising=False)
    return path


def test_refund_parks(tmp_path, monkeypatch):
    path = _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    cfg = {"configurable": {"thread_id": "test-11-park"}}
    graph.invoke({"ticket": REFUND_TICKET}, cfg)
    state = graph.get_state(cfg)
    assert state.interrupts
    payload = state.interrupts[0].value
    assert payload["action"] == "refund"
    assert payload["order_id"] == "DF-1001"
    assert payload["amount"] == 49.0
    assert "question" in payload
    assert not path.exists()
    assert refund_mod.read_refunds() == []


def test_lookup_does_not_park(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(model=FakeChatModel(route="lookup"))
    cfg = {"configurable": {"thread_id": "test-11-lookup"}}
    out = graph.invoke({"ticket": LOOKUP_TICKET}, cfg)
    state = graph.get_state(cfg)
    assert not state.interrupts
    assert out.get("route") == "lookup"
    assert "looked up" in (out.get("reply") or "")
    assert out.get("order", {}).get("found") is True


def test_resume_approve(tmp_path, monkeypatch):
    path = _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    cfg = {"configurable": {"thread_id": "test-11-approve"}}
    graph.invoke({"ticket": REFUND_TICKET}, cfg)
    assert refund_mod.read_refunds() == []
    done = resume_with(graph, cfg, "approve")
    assert done.get("decision") == "approve"
    assert "issued" in (done.get("reply") or "").lower()
    rows = refund_mod.read_refunds()
    assert len(rows) == 1
    assert rows[0]["refunded"] is True
    assert rows[0]["order_id"] == "DF-1001"
    assert rows[0]["amount"] == 49.0
    assert path.is_file()


def test_resume_reject(tmp_path, monkeypatch):
    path = _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    cfg = {"configurable": {"thread_id": "test-11-reject"}}
    graph.invoke({"ticket": REFUND_TICKET}, cfg)
    done = resume_with(graph, cfg, "reject")
    assert done.get("decision") == "reject"
    assert "declined" in (done.get("reply") or "").lower()
    assert refund_mod.read_refunds() == []
    assert not path.exists()


def test_edit_before_resume(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    cfg = {"configurable": {"thread_id": "test-11-edit"}}
    graph.invoke({"ticket": REFUND_TICKET}, cfg)
    payload = graph.get_state(cfg).interrupts[0].value
    assert payload["amount"] == 49.0
    done = resume_with(graph, cfg, {"amount": 20.0})
    rows = refund_mod.read_refunds()
    assert len(rows) == 1
    assert rows[0]["amount"] == 20.0
    assert rows[0]["order_id"] == "DF-1001"
    assert "20.0" in str(done.get("reply"))


def test_write_is_after_interrupt(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    cfg = {"configurable": {"thread_id": "test-11-twice"}}
    graph.invoke({"ticket": REFUND_TICKET}, cfg)
    assert refund_mod.read_refunds() == []
    resume_with(graph, cfg, "approve")
    assert len(refund_mod.read_refunds()) == 1
    try:
        resume_with(graph, cfg, "approve")
    except Exception:
        pass
    assert len(refund_mod.read_refunds()) == 1
