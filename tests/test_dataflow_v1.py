"""6.1 DataFlow v1 triage graph. Pytest stays green with no live model."""

from dataflow.graphs.v1_triage import build_v1_triage, classify
from tests.fixtures.fake_model import FakeChatModel


def test_compiles():
    graph = build_v1_triage()
    drawing = graph.get_graph().draw_mermaid()
    assert "classify" in drawing
    assert "lookup" in drawing
    assert "reply" in drawing
    assert "__start__" in drawing or "start" in drawing.lower()


def test_classify_returns_route():
    out = classify(
        {"ticket": "Where is order DF-1001?"},
        model=FakeChatModel(),
    )
    assert out["route"] in {"orders", "policy", "escalate"}
    assert out["route"] == "orders"


def test_invoke_finds_order():
    graph = build_v1_triage(model=FakeChatModel())
    out = graph.invoke({"ticket": "Where is order DF-1001?"})
    assert out["order"]["found"] is True
    assert out["order"]["order_id"] == "DF-1001"
    assert out["order"]["item"] == "desk lamp"
    assert "DF-1001" in out["reply"]


def test_unknown_order_is_a_miss():
    graph = build_v1_triage(model=FakeChatModel())
    out = graph.invoke({"ticket": "Where is order DF-9999?"})
    assert out["order"]["found"] is False
    assert out["order"]["order_id"] == "DF-9999"
    assert "could not find" in out["reply"].lower()
