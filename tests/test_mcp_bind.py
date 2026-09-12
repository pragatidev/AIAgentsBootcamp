"""13.1.6 MCPAdapter bind. Pytest stays green with the fixture model."""

from langchain_core.messages import HumanMessage

from dataflow.mcp.bind import bind_mcp_tools, bound_names, build_desk, close_mcp
from tests.fixtures.fake_model import FakeToolModel


def test_bound_names_include_lookup_order():
    try:
        tools = bind_mcp_tools()
        names = bound_names(tools)
        assert "lookup_order" in names
        assert "refund" in names
    finally:
        close_mcp()


def test_desk_calls_lookup_order_with_fixture_model():
    try:
        tools = bind_mcp_tools()
        graph = build_desk(model=FakeToolModel(), tools=tools)
        out = graph.invoke(
            {"messages": [HumanMessage(content="Where is order DF-1001?")]}
        )
        messages = list(out.get("messages") or [])
        names = []
        for message in messages:
            for call in list(getattr(message, "tool_calls", None) or []):
                names.append(call.get("name"))
        assert "lookup_order" in names
        texts = " ".join(str(getattr(m, "content", "")) for m in messages)
        assert "DF-1001" in texts
    finally:
        close_mcp()
