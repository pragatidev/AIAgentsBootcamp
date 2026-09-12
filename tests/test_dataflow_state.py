"""6.3 DataFlow state and reducers. Pytest stays green with no live model."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import InvalidUpdateError

from dataflow.graphs.collision import build_collision, build_collision_fixed
from dataflow.graphs.messages import build_messages_graph
from dataflow.graphs.trim import build_trim_graph, count_message_tokens
from tests.fixtures.fake_model import FakeChatModel


def test_messages_accumulate():
    graph = build_messages_graph(model=FakeChatModel(reply="looked up desk lamp"))
    first = graph.invoke(
        {"messages": [HumanMessage(content="Where is order DF-1001?")]}
    )
    messages = first["messages"]
    assert len(messages) >= 3
    kinds = [getattr(m, "type", "") for m in messages]
    assert "human" in kinds
    assert "ai" in kinds
    follow = list(messages) + [
        HumanMessage(content="What about the return window?")
    ]
    second = graph.invoke({"messages": follow})
    assert len(second["messages"]) > len(messages)
    assert len(second["messages"]) == len(follow) + 2


def test_collision_raises():
    with pytest.raises(InvalidUpdateError):
        build_collision().invoke({"ticket": "DF-1001", "log": ""})


def test_reducer_keeps_both():
    out = build_collision_fixed().invoke({"ticket": "DF-1001", "log": []})
    log = out["log"]
    assert "orders looked up" in log
    assert "policy read" in log


def test_trim_under_budget():
    model = FakeChatModel(
        reply="Customer asked about several DataFlow orders and the 30 day return window."
    )
    messages = []
    for i in range(12):
        messages.append(
            HumanMessage(
                content=(
                    f"Turn {i}: Where is order DF-1001? "
                    "The lamp is unused and I want the 30 day window applied. "
                    "Please check billing and shipping too."
                )
            )
        )
        messages.append(
            AIMessage(
                content=(
                    f"Noted turn {i}. Order DF-1001 is on the desk. "
                    "Return window is 30 days for unused items."
                )
            )
        )
    before = count_message_tokens(messages)
    out = build_trim_graph(model=model).invoke({"messages": messages})
    after = count_message_tokens(out["messages"])
    assert before > 0
    assert after < before
    assert out.get("summary")
