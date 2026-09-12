"""6.12 ambient watcher, inbox, and nightly triage. Pytest stays green with no live model."""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from dataflow.ambient.inbox import list_parked, resolve
from dataflow.ambient.watcher import on_new_ticket, watch
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.graphs import v8_nightly as v8_mod
from dataflow.graphs.v8_nightly import build_v8_nightly
from dataflow.tools import refund as refund_mod
from tests.fixtures.fake_model import FakeChatModel

LOOKUP = {
    "ticket_id": "T-3002",
    "customer_id": "C-2002",
    "text": "Where is order DF-1002? Tracking still says in transit.",
}
REFUND_A = {
    "ticket_id": "T-3001",
    "customer_id": "C-2001",
    "text": "Hi, I want to return order DF-1001. The desk lamp is unused. Can I get a refund?",
}
REFUND_B = {
    "ticket_id": "T-3009",
    "customer_id": "C-2009",
    "text": "Order DF-1009 arrived damaged. I want a replacement or a refund.",
}


def _patch_refunds(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    monkeypatch.delenv("DATAFLOW_REFUNDS_PATH", raising=False)
    return path


def _write_ticket(folder, row):
    path = folder / (row["ticket_id"] + ".json")
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return path


def _thread(name: str) -> dict:
    return {"configurable": {"thread_id": name}}


def test_watcher_starts_run(tmp_path):
    folder = tmp_path / "drop"
    folder.mkdir()
    _write_ticket(folder, LOOKUP)
    graph = build_v4_hitl(model=FakeChatModel(route="lookup"))
    out = on_new_ticket(folder / "T-3002.json", graph)
    assert out["thread_id"] == "T-3002"
    assert out["parked"] is False
    assert out.get("reply")


def test_watcher_parks_refund(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    folder = tmp_path / "drop"
    folder.mkdir()
    path = _write_ticket(folder, REFUND_A)
    saver = InMemorySaver()
    graph = build_v4_hitl(checkpointer=saver, model=FakeChatModel(route="refund"))
    out = on_new_ticket(path, graph, checkpointer=saver)
    assert out["parked"] is True
    assert out["thread_id"] == "T-3001"
    snap = graph.get_state(_thread("T-3001"))
    assert snap.interrupts
    assert snap.interrupts[0].value["action"] == "refund"


def test_inbox_lists_parked(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    folder = tmp_path / "drop"
    folder.mkdir()
    _write_ticket(folder, REFUND_A)
    _write_ticket(folder, REFUND_B)
    saver = InMemorySaver()
    graph = build_v4_hitl(checkpointer=saver, model=FakeChatModel(route="refund"))
    watch(folder, graph, once=True)
    rows = list_parked(saver, graph)
    ids = {row["thread_id"] for row in rows}
    assert ids == {"T-3001", "T-3009"}
    assert len(rows) == 2
    for row in rows:
        assert row.get("payload")
        assert row.get("ticket")


def test_inbox_resolves(tmp_path, monkeypatch):
    path = _patch_refunds(tmp_path, monkeypatch)
    folder = tmp_path / "drop"
    folder.mkdir()
    _write_ticket(folder, REFUND_A)
    _write_ticket(folder, REFUND_B)
    saver = InMemorySaver()
    graph = build_v4_hitl(checkpointer=saver, model=FakeChatModel(route="refund"))
    watch(folder, graph, once=True)
    done = resolve(graph, "T-3001", "approve", actor="reviewer-anna")
    assert "issued" in (done.get("reply") or "").lower()
    rows = refund_mod.read_refunds()
    assert len(rows) == 1
    assert rows[0]["order_id"] == "DF-1001"
    assert path.is_file()
    parked = list_parked(saver, graph)
    ids = {row["thread_id"] for row in parked}
    assert ids == {"T-3009"}
    other = graph.get_state(_thread("T-3009"))
    assert other.interrupts


def test_resolve_carries_actor(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    folder = tmp_path / "drop"
    folder.mkdir()
    _write_ticket(folder, REFUND_A)
    saver = InMemorySaver()
    graph = build_v4_hitl(checkpointer=saver, model=FakeChatModel(route="refund"))
    watch(folder, graph, once=True)
    resolve(graph, "T-3001", "approve", actor="reviewer-anna")
    snap = graph.get_state(_thread("T-3001"))
    assert snap.values.get("actor") == "reviewer-anna"


def test_nightly_report_written(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    tickets = tmp_path / "tickets.jsonl"
    rows = [
        {**LOOKUP, "created_at": "2026-08-03T11:02:00Z"},
        {
            "ticket_id": "T-3003",
            "customer_id": "C-2003",
            "text": "What is your return window? I cannot find it on the site.",
            "created_at": "2026-08-03T15:40:00Z",
        },
    ]
    tickets.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )
    reports = tmp_path / "reports"
    monkeypatch.setattr(v8_mod, "TICKETS_PATH", tickets)
    monkeypatch.setattr(v8_mod, "REPORTS_DIR", reports)
    saver = InMemorySaver()
    graph = build_v8_nightly(
        checkpointer=saver,
        model=FakeChatModel(route="lookup"),
        max_workers=20,
    )
    out = graph.invoke({"date": "2026-08-03"}, _thread("nightly-2026-08-03"))
    report_path = Path(out.get("report_path") or "")
    assert report_path.is_file()
    body = report_path.read_text(encoding="utf-8")
    assert "tickets: 2" in body
    assert "answered: 2" in body
    assert "parked: 0" in body
    assert "skipped: 0" in body


def test_nightly_fan_capped(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    tickets = tmp_path / "tickets.jsonl"
    rows = [
        {**LOOKUP, "ticket_id": "T-A", "created_at": "2026-08-03T11:00:00Z"},
        {**LOOKUP, "ticket_id": "T-B", "created_at": "2026-08-03T12:00:00Z"},
        {**LOOKUP, "ticket_id": "T-C", "created_at": "2026-08-03T13:00:00Z"},
    ]
    tickets.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )
    reports = tmp_path / "reports"
    monkeypatch.setattr(v8_mod, "TICKETS_PATH", tickets)
    monkeypatch.setattr(v8_mod, "REPORTS_DIR", reports)
    saver = InMemorySaver()
    graph = build_v8_nightly(
        checkpointer=saver,
        model=FakeChatModel(route="lookup"),
        max_workers=2,
    )
    out = graph.invoke({"date": "2026-08-03"}, _thread("nightly-2026-08-03-cap"))
    skipped = [r for r in (out.get("results") or []) if r.get("skipped")]
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "fan cap"
    body = Path(out["report_path"]).read_text(encoding="utf-8")
    assert "skipped: 1" in body
    assert "tickets: 3" in body
