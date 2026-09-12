"""S9-S16 spine. No API key."""

from langgraph.errors import InvalidUpdateError
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from dataflow.graphs.collision import build_collision, build_reduced
from dataflow.graphs.runaway import run_with_cap
from dataflow.graphs.trim import trim_messages
from dataflow.graphs.v2_route import build_v2_route
from tests.fixtures.fake_model import FakeChatModel
from dataflow.graphs.v3_memory import (
    build_v3_memory,
    read_preference,
    remember_preference,
)
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools.retrieve import retrieve
from dataflow.tools.structured import parse_tool_json


def test_routes_three_ways():
    orders = build_v2_route(model=FakeChatModel(route="orders")).invoke(
        {"ticket": "Can I return order DF-1001?"}
    )
    policy = build_v2_route(model=FakeChatModel(route="policy")).invoke(
        {"ticket": "What is your shipping time?"}
    )
    human = build_v2_route(model=FakeChatModel(route="escalate")).invoke(
        {"ticket": "I want a human manager please"}
    )
    assert orders["route"] == "orders"
    assert orders["order"]["found"] is True
    assert policy["route"] == "policy"
    assert policy.get("policy") is not None
    assert human["route"] == "escalate"
    assert human["escalation"]["parked"] is True


def test_collision_then_reducer():
    try:
        build_collision().invoke({"ticket": "DF-1001", "log": ""})
        raise AssertionError("collision should raise")
    except InvalidUpdateError:
        pass
    out = build_reduced().invoke({"ticket": "DF-1001", "log": []})
    assert sorted(out["log"]) == ["orders looked up", "policy read"]


def test_trim_keeps_last_four():
    assert trim_messages(["a", "b", "c", "d", "e"], keep=4) == ["b", "c", "d", "e"]


def test_checkpoint_accrues_turns():
    graph = build_v3_memory()
    cfg = {"configurable": {"thread_id": "t1"}}
    graph.invoke({"ticket": "one"}, cfg)
    second = graph.invoke({"ticket": "two"}, cfg)
    assert second["turns"] == 2
    assert second["last_ticket"] == "two"


def test_store_is_cross_thread():
    store = InMemoryStore()
    remember_preference(store, "cust-1", "channel", "email")
    assert read_preference(store, "cust-1", "channel") == "email"
    assert read_preference(store, "cust-2", "channel") is None


def test_lookup_does_not_park_refund_does():
    graph = build_v4_hitl()
    look = graph.invoke(
        {"ticket": "Status of order DF-1001?"},
        {"configurable": {"thread_id": "l1"}},
    )
    assert "looked up" in look.get("reply", "")
    parked = graph.invoke(
        {"ticket": "Please refund order DF-1001"},
        {"configurable": {"thread_id": "r1"}},
    )
    state = graph.get_state({"configurable": {"thread_id": "r1"}})
    assert state.interrupts
    assert state.interrupts[0].value["action"] == "refund"
    done = graph.invoke(Command(resume="approve"), {"configurable": {"thread_id": "r1"}})
    assert done["decision"] == "approve"


def test_retrieve_hit_and_refuse():
    hit = retrieve("Can I return an unused item after delivery?")
    assert hit["found"] is True
    assert hit["hits"][0]["path"] == "return_policy.md"
    miss = retrieve("What is the weather on Mars?")
    assert miss["refuse"] is True


def test_parse_fail_closed():
    assert parse_tool_json('{"found": true}')["ok"] is True
    assert parse_tool_json("not json")["fail_closed"] is True


def test_runaway_hits_recursion_limit():
    out = run_with_cap(8)
    assert out["stopped"] is True
    assert out["reason"] == "recursion_limit"
