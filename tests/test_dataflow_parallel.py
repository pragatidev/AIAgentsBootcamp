"""6.7 DataFlow fan-out. Pytest stays green with no live model."""

import pytest
from langgraph.errors import InvalidUpdateError

from dataflow.graphs.v6_parallel import (
    build_v6_parallel,
    build_v6_parallel_no_reducer,
)
from tests.fixtures.fake_model import FakeChatModel

TICKET = "Hi, I want to return order DF-1001. The desk lamp is unused. Can I get a refund?"


def _thread(name: str) -> dict:
    return {"configurable": {"thread_id": name}}


def _names_in_snapshot(snap) -> set[str]:
    names: set[str] = set()
    meta = snap.metadata or {}
    writes = meta.get("writes") or {}
    if isinstance(writes, dict):
        names.update(str(k) for k in writes if not str(k).startswith("__"))
    names.update(str(n) for n in (snap.next or ()))
    names.update(str(t.name) for t in (snap.tasks or ()))
    return names


def test_fanout_one_superstep():
    model = FakeChatModel(
        route="orders",
        reply="Order DF-1001 is delivered. The return window is 30 days.",
    )
    graph = build_v6_parallel(model=model)
    cfg = _thread("test-13-2-superstep")
    graph.invoke({"ticket": TICKET}, cfg)
    history = list(graph.get_state_history(cfg))
    found_both = False
    for snap in history:
        names = _names_in_snapshot(snap)
        if "lookup" in names and "policy_search" in names:
            found_both = True
            break
    assert found_both


def test_fanout_without_reducer_collides():
    model = FakeChatModel(route="orders", reply="looked up desk lamp")
    with pytest.raises(InvalidUpdateError, match="one value"):
        build_v6_parallel_no_reducer(model=model).invoke({"ticket": TICKET})


def test_join_sees_both_results():
    model = FakeChatModel(
        route="orders",
        reply="Order DF-1001 is delivered. The return window is 30 days.",
    )
    graph = build_v6_parallel(model=model)
    cfg = _thread("test-13-2-join")
    graph.invoke({"ticket": TICKET}, cfg)
    before_join = None
    for snap in graph.get_state_history(cfg):
        if tuple(snap.next) == ("draft_reply",):
            before_join = snap
            break
    assert before_join is not None
    results = list((before_join.values or {}).get("results") or [])
    sources = {row.get("source") for row in results}
    assert "lookup" in sources
    assert "policy" in sources
    assert len(results) == 2
