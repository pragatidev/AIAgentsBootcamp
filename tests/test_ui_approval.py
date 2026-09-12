"""14.2 DataFlow approval screen and inbox. Pytest stays green with no live model."""

from langgraph.checkpoint.memory import InMemorySaver

from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools import refund as refund_mod
from dataflow.ui.desk_core import (
    approve,
    edit,
    inbox_rows,
    reject,
    stream_tokens,
)
from tests.fixtures.fake_model import FakeChatModel

REFUND_A = "Please refund order DF-1001, the lamp is unused"
REFUND_B = "Order DF-1009 arrived damaged. I want a refund."


def _patch_refunds(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    return path


def _park(graph, ticket, thread_id):
    list(stream_tokens(graph, ticket, thread_id))
    snap = graph.get_state({"configurable": {"thread_id": thread_id}})
    assert snap.interrupts


def test_approve_writes_one_row(tmp_path, monkeypatch):
    path = _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(
        checkpointer=InMemorySaver(),
        model=FakeChatModel(route="refund"),
    )
    _park(graph, REFUND_A, "ui-approve")
    assert refund_mod.read_refunds() == []
    done = approve(graph, "ui-approve")
    rows = refund_mod.read_refunds()
    assert len(rows) == 1
    assert rows[0]["order_id"] == "DF-1001"
    assert rows[0]["refunded"] is True
    assert path.is_file()
    refund = done.get("refund") or {}
    assert refund.get("refunded") is True
    assert refund.get("order_id") == "DF-1001"


def test_reject_writes_none_and_returns_miss(tmp_path, monkeypatch):
    path = _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(
        checkpointer=InMemorySaver(),
        model=FakeChatModel(route="refund"),
    )
    _park(graph, REFUND_A, "ui-reject")
    done = reject(graph, "ui-reject", "lamp was used")
    rows = refund_mod.read_refunds()
    assert rows == []
    assert not path.exists()
    refund = done.get("refund") or {}
    assert refund.get("refunded") is False
    assert refund.get("declined") is True
    assert "declined" in (done.get("reply") or "").lower()


def test_edit_changes_the_amount(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    graph = build_v4_hitl(
        checkpointer=InMemorySaver(),
        model=FakeChatModel(route="refund"),
    )
    _park(graph, REFUND_A, "ui-edit")
    done = edit(graph, "ui-edit", {"amount": 20.0, "reason": "partial refund"})
    rows = refund_mod.read_refunds()
    assert len(rows) == 1
    assert rows[0]["amount"] == 20.0
    refund = done.get("refund") or {}
    assert refund.get("amount") == 20.0
    assert "20.0" in str(done.get("reply"))


def test_inbox_rows_two_parked_resolve_one_leaves_the_other(tmp_path, monkeypatch):
    _patch_refunds(tmp_path, monkeypatch)
    saver = InMemorySaver()
    graph = build_v4_hitl(
        checkpointer=saver,
        model=FakeChatModel(route="refund"),
    )
    _park(graph, REFUND_A, "thread-A")
    _park(graph, REFUND_B, "thread-B")
    rows = inbox_rows(saver, graph)
    ids = {row["thread_id"] for row in rows}
    assert ids == {"thread-A", "thread-B"}
    assert len(rows) == 2
    for row in rows:
        assert row.get("payload")
        assert "age_seconds" in row
    approve(graph, "thread-A")
    left = inbox_rows(saver, graph)
    left_ids = {row["thread_id"] for row in left}
    assert left_ids == {"thread-B"}
    other = graph.get_state({"configurable": {"thread_id": "thread-B"}})
    assert other.interrupts
