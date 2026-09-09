"""S8.4 Classify node and a full invoke. No model."""

from northstar.graphs.v1_triage import build_v1_triage, classify


def test_classify_return_goes_to_orders():
    out = classify({"ticket": "Can I return order NS-1001?"})
    assert out["route"] == "orders"


def test_classify_other_goes_to_policy():
    out = classify({"ticket": "What is your shipping time?"})
    assert out["route"] == "policy"


def test_invoke_finds_desk_lamp():
    graph = build_v1_triage()
    out = graph.invoke({"ticket": "Can I return order NS-1001?"})
    assert out["route"] == "orders"
    assert out["order"]["found"] is True
    assert out["order"]["item"] == "desk lamp"
    assert "NS-1001" in out["reply"]


def test_invoke_unknown_order():
    graph = build_v1_triage()
    out = graph.invoke({"ticket": "Can I return order NS-9999?"})
    assert out["order"]["found"] is False
    assert "could not find" in out["reply"]
