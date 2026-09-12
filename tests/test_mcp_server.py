"""13.1.3 FastMCP server. Pytest stays green with no live model."""

from dataflow.mcp.server import (
    call_tool,
    list_tool_schemas,
    read_returns_policy,
    render_decline,
)


def test_lookup_in_process():
    row = call_tool("lookup_order", {"order_id": "DF-1001"})
    assert row["found"] is True
    assert row["order_id"] == "DF-1001"
    assert row["item"] == "desk lamp"


def test_unknown_table_is_a_miss():
    row = call_tool("lookup_order", {"order_id": "DF-1001", "table": "customers"})
    assert row["found"] is False
    assert row["reason"] == "unknown table"


def test_returns_resource_starts_with_heading():
    text = read_returns_policy()
    assert text.startswith("# DataFlow return policy")


def test_decline_prompt_renders():
    text = render_decline("DF-1001", "outside the window")
    assert "DF-1001" in text
    assert "outside the window" in text


def test_lookup_schema_has_table():
    schemas = {row["name"]: row["input_schema"] for row in list_tool_schemas()}
    assert "lookup_order" in schemas
    props = (schemas["lookup_order"] or {}).get("properties") or {}
    assert "order_id" in props
    assert "table" in props
