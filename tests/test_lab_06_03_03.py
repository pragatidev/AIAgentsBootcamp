"""Lab 06.03.03 (12.3), ChatState and build_chat typed by the student. A scripted model stands in for the real one
here, and only here."""

import runpy
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

import config
from dataflow.graphs.messages import build_messages_graph
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_03_03_add_messages_on_the_thread.py"
REDUCER = "    messages: Annotated[list, add_messages]\n"
REPLY = "Order DF-1001 is noted."


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(reply=REPLY))


def _counts(lines):
    return [int(line.split()[1]) for line in lines if line.startswith("  count ")]


def _edges(graph):
    return {(e.source, e.target, e.conditional) for e in graph.get_graph().edges}


def _shape(messages):
    return [(m.type, m.name, m.content) for m in messages]


def test_lab_grows_the_thread_and_replaces_by_id(scripted, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "nodes ['__start__', 'agent', 'take_note', '__end__']" in out
    assert _counts(out) == [1, 2, 3, 4, 5, 6]
    newest = [line.split("newest ")[1] for line in out if line.startswith("  count ")]
    assert newest == ["human ", "ai ", "ai note"] * 2
    assert "thread_count 6" in out
    assert "5 ai note desk note: recorded the ticket (Quick one: can I add a warranty to DF-1001 after delivery?)" in out
    assert "count_after_replace 6" in out
    assert "last note desk note: warranty question sent to the orders team" in out
    assert out[-1] == "same_id True"


def test_typed_graph_matches_the_package(scripted):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    mine = lab["build_chat"](model=FakeChatModel(reply=REPLY))
    package = build_messages_graph(model=FakeChatModel(reply=REPLY))
    assert set(mine.get_graph().nodes) == set(package.get_graph().nodes)
    assert _edges(mine) == _edges(package)
    start = {"messages": [HumanMessage(content="Where is order DF-1002?")]}
    assert _shape(mine.invoke(start)["messages"]) == _shape(package.invoke(start)["messages"])


def test_break_no_reducer_keeps_only_the_last_write(scripted, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, REDUCER, "    messages: list\n")
    runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert _counts(out) == [1, 1, 1, 1, 1, 1]
    assert "thread_count 1" in out
    assert "0 ai note desk note: recorded the ticket ()" in out
    assert "count_after_replace 1" in out
