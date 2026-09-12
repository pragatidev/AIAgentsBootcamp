"""6.2 DataFlow routing. Pytest stays green with no live model."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from dataflow.graphs.v2_command import build_v2_command
from dataflow.graphs.v2_route import build_v2_route, pick_route
from dataflow.graphs.v2_tools import build_v2_tools
from tests.fixtures.fake_model import FakeChatModel, FakeToolModel


def test_route_orders():
    graph = build_v2_route(model=FakeChatModel(route="orders"))
    out = graph.invoke({"ticket": "Where is order DF-1001?"})
    assert out["route"] == "orders"
    assert out["order"]["found"] is True
    assert out["order"]["order_id"] == "DF-1001"
    assert "DF-1001" in out["reply"]
    drawing = graph.get_graph().draw_mermaid()
    assert "orders_desk" in drawing
    assert "policy_desk" in drawing
    assert "escalate_desk" in drawing


def test_route_policy():
    graph = build_v2_route(model=FakeChatModel(route="policy"))
    out = graph.invoke({"ticket": "What is your return window?"})
    assert out["route"] == "policy"
    assert out.get("policy") is not None
    assert out.get("reply")


def test_route_escalate():
    graph = build_v2_route(model=FakeChatModel(route="escalate"))
    out = graph.invoke({"ticket": "I want a manager on the phone today."})
    assert out["route"] == "escalate"
    assert out["escalation"]["parked"] is True
    assert out["escalation"]["status"] == "ticket-parked"
    assert "parked" in out["reply"].lower()


def test_tool_cycle_ends():
    graph = build_v2_tools(model=FakeToolModel())
    out = graph.invoke(
        {"messages": [HumanMessage(content="Where is order DF-1001?")]}
    )
    messages = out["messages"]
    assert any(isinstance(m, ToolMessage) for m in messages)
    assert isinstance(messages[-1], AIMessage)
    assert not (getattr(messages[-1], "tool_calls", None) or [])


def test_command_routes_same_as_edge():
    ticket = {"ticket": "Where is order DF-1001?"}
    for route in ("orders", "policy", "escalate"):
        model = FakeChatModel(route=route)
        edge = build_v2_route(model=model).invoke(ticket)
        cmd = build_v2_command(model=model).invoke(ticket)
        assert edge["route"] == cmd["route"] == route
        assert edge["reply"] == cmd["reply"]


def test_pick_route_reads_state():
    assert pick_route({"route": "orders"}) == "orders"
    assert pick_route({"route": "policy"}) == "policy"
    assert pick_route({"route": "escalate"}) == "escalate"
