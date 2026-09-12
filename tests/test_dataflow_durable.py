"""6.8 DataFlow retries, cache, defer, and the receipt task. No live model."""

from __future__ import annotations

import time

import pytest
from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.sqlite import SqliteSaver

import dataflow.graphs.durable as durable
from dataflow.graphs.durable import (
    build_durable,
    build_two_length_fan,
    count_receipts,
    set_crash_after_receipt,
)
from dataflow.tools.flaky import reset_flaky, set_always_fail
from tests.fixtures.fake_model import FakeChatModel

TICKET_3002 = "Where is order DF-1002? Tracking still says in transit."
TICKET_3003 = "What is your return window? I cannot find it on the site."


def _thread(name: str) -> dict:
    return {"configurable": {"thread_id": name}}


@pytest.fixture
def receipts_dir(tmp_path, monkeypatch):
    path = tmp_path / "receipts.jsonl"
    monkeypatch.setattr(durable, "RECEIPTS_PATH", path)
    monkeypatch.setenv("DATAFLOW_RECEIPTS_PATH", str(path))
    return path


def _model(reply: str = "Order DF-1002 is in transit. The return window is 30 days."):
    return FakeChatModel(reply=reply)


def test_retry_then_success(receipts_dir):
    reset_flaky()
    durable.reset_durable()
    graph = build_durable(model=_model())
    out = graph.invoke({"ticket": TICKET_3002}, _thread("test-14-retry"))
    log = list(out.get("log") or [])
    assert "attempt 1 timeout" in log
    assert "attempt 2 timeout" in log
    assert "attempt 3 success" in log
    assert log.count("attempt 1 timeout") == 1
    assert log.count("attempt 2 timeout") == 1
    assert log.count("attempt 3 success") == 1
    carrier = out.get("carrier") or {}
    assert carrier.get("found") is True
    assert carrier.get("order_id") == "DF-1002"
    assert carrier.get("status") == "in_transit"
    assert carrier.get("item") == "USB-C hub"
    assert out.get("reply")


def test_error_handler_typed_miss(receipts_dir):
    reset_flaky()
    set_always_fail(True)
    durable.reset_durable()
    graph = build_durable(
        model=_model("Carrier is down. The return window is 30 days.")
    )
    out = graph.invoke({"ticket": TICKET_3002}, _thread("test-14-miss"))
    carrier = out.get("carrier") or {}
    assert carrier.get("found") is False
    assert carrier.get("reason") == "carrier unreachable after retries"
    assert out.get("reply")
    assert out.get("policy")


def test_cache_skips(receipts_dir):
    reset_flaky()
    durable.reset_durable()
    cache = InMemoryCache()
    graph = build_durable(model=_model("The return window is 30 days."), cache=cache)
    graph.invoke({"ticket": TICKET_3003}, _thread("test-14-cache-a"))
    assert durable.POLICY_CALLS == 1
    graph.invoke({"ticket": TICKET_3003}, _thread("test-14-cache-b"))
    assert durable.POLICY_CALLS == 1


def test_cache_expires(receipts_dir):
    reset_flaky()
    durable.reset_durable()
    cache = InMemoryCache()
    graph = build_durable(
        model=_model("The return window is 30 days."),
        cache=cache,
        cache_ttl=1,
    )
    graph.invoke({"ticket": TICKET_3003}, _thread("test-14-ttl-a"))
    assert durable.POLICY_CALLS == 1
    time.sleep(1.2)
    graph.invoke({"ticket": TICKET_3003}, _thread("test-14-ttl-b"))
    assert durable.POLICY_CALLS == 2


def test_defer_runs_once():
    off = build_two_length_fan(defer=False).invoke({})
    on = build_two_length_fan(defer=True).invoke({})
    assert len(on.get("runs") or []) == 1
    assert len(off.get("runs") or []) == 2


def test_task_not_repeated_on_resume(receipts_dir, tmp_path):
    reset_flaky()
    durable.reset_durable()
    db = tmp_path / "checkpoints_14.sqlite"
    model = _model()
    with SqliteSaver.from_conn_string(str(db)) as saver:
        saver.setup()
        graph = build_durable(checkpointer=saver, model=model)
        set_crash_after_receipt(True)
        with pytest.raises(RuntimeError, match="planted crash after the receipt task"):
            graph.invoke({"ticket": TICKET_3002}, _thread("test-14-task"))
        assert count_receipts() == 1
        set_crash_after_receipt(False)
        out = graph.invoke(None, _thread("test-14-task"))
        assert count_receipts() == 1
        assert out.get("reply")
