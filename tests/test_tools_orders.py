"""S6.5 One happy path, one miss."""

from northstar.tools.orders import lookup_order_by_id, lookup_order_tool


def test_known_order():
    row = lookup_order_by_id("NS-1001")
    assert row["found"] is True
    assert row["item"] == "desk lamp"


def test_unknown_order_is_a_miss_not_a_crash():
    row = lookup_order_by_id("NS-9999")
    assert row["found"] is False
    assert row["reason"] == "unknown order"


def test_langchain_tool_schema():
    assert lookup_order_tool.name == "lookup_order_tool"
    assert "NS-1001" in lookup_order_tool.description
    assert "order_id" in lookup_order_tool.args
