"""S9.5 Two fixtures, two routes. Classify alone, then the compiled graph."""

from dataflow.graphs.v2_route import build_v2_route, classify
from tests.fixtures.fake_model import FakeChatModel


def test_classify_return_goes_to_orders():
    out = classify(
        {"ticket": "Can I return order DF-1001?"},
        model=FakeChatModel(route="orders"),
    )
    assert out["route"] == "orders"


def test_classify_shipping_goes_to_policy():
    out = classify(
        {"ticket": "What is your shipping time?"},
        model=FakeChatModel(route="policy"),
    )
    assert out["route"] == "policy"


def test_invoke_return_hits_orders():
    out = build_v2_route(model=FakeChatModel(route="orders")).invoke(
        {"ticket": "Can I return order DF-1001?"}
    )
    assert out["route"] == "orders"
    assert out["order"]["found"] is True
    assert out["order"]["item"] == "desk lamp"


def test_invoke_human_escalates():
    out = build_v2_route(model=FakeChatModel(route="escalate")).invoke(
        {"ticket": "I want a human manager please"}
    )
    assert out["route"] == "escalate"
    assert out["escalation"]["parked"] is True
