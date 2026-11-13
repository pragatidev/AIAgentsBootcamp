"""Lab 06.02.04 (11.4), build_tool_cycle typed by the student. A scripted tool model stands in for the real one here,
and only here."""

import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError

import config
from dataflow.graphs.v2_tools import build_v2_tools
from tests.fixtures.fake_model import ScriptedToolChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_02_04_tool_cycle.py"
EDGE_BACK = '    builder.add_edge("tools", "agent")\n'


def _call(name, args, cid):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid, "type": "tool_call"}])


def _script():
    return [_call("lookup_order", {"order_id": "DF-1002"}, "c1"), AIMessage(content="DF-1002 is in transit.")]


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: ScriptedToolChatModel(script=_script()))


def _edges(graph):
    return {(e.source, e.target, e.conditional) for e in graph.get_graph().edges}


def test_lab_prints_every_message_in_order(scripted, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "nodes ['__start__', 'agent', 'tools', '__end__']" in out
    assert "\ttools --> agent;" in out
    assert out[-6:] == [
        "0 human Where is order DF-1002? Tracking still says in transit.",
        '1 ai calls [["lookup_order", {"order_id": "DF-1002"}]] ',
        out[-4],
        '3 ai calls [] DF-1002 is in transit.',
        "message_count 4",
        "last_is_answer True",
    ]
    assert out[-4].startswith('2 tool lookup_order {"found": true, "order_id": "DF-1002"')


def test_typed_cycle_matches_the_package(scripted):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    mine = lab["build_tool_cycle"](model=ScriptedToolChatModel(script=_script()))
    package = build_v2_tools(model=ScriptedToolChatModel(script=_script()))
    assert set(mine.get_graph().nodes) == set(package.get_graph().nodes)
    assert _edges(mine) == _edges(package)
    ticket = {"messages": [HumanMessage(content="Where is order DF-1002?")]}
    assert [m.type for m in mine.invoke(ticket)["messages"]] == [m.type for m in package.invoke(ticket)["messages"]]


def test_break_no_edge_back_ends_on_the_tool_message(scripted, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, EDGE_BACK, "")
    runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[-3].startswith('2 tool lookup_order {"found": true, "order_id": "DF-1002"')
    assert out[-2:] == ["message_count 3", "last_is_answer False"]
    assert "	tools --> __end__;" in out and "	tools --> agent;" not in out


def test_a_model_that_always_calls_a_tool_hits_the_cap(scripted):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    always = ScriptedToolChatModel(script=[_call("lookup_order", {"order_id": "DF-1002"}, f"c{i}") for i in range(40)])
    with pytest.raises(GraphRecursionError, match="Recursion limit of 10 reached"):
        lab["build_tool_cycle"](model=always).invoke({"messages": [HumanMessage(content="Where is order DF-1002?")]})
    assert always.calls == 5
