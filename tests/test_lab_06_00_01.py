"""Lab 06.00.01 (9.1), where the desk runs out of road. A scripted tool model and a hashing index stand in for the
real ones here, and only here."""

import importlib
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from dataflow.rag.faiss_index import build_faiss_index
from dataflow.rag.load import WIKI_DIR, load_knowledge_base
from tests.fixtures.fake_model import ScriptedToolChatModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings

RT = importlib.import_module("dataflow.tools.retrieve")
LAB = Path(__file__).resolve().parents[1] / "labs" / "06_00_01_where_the_desk_runs_out.py"
LOOP = "road model -> ToolCallLimitMiddleware.after_model -> tools -> model -> ToolCallLimitMiddleware.after_model"


def _call(name, args, cid):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid, "type": "tool_call"}])


SCRIPT = [
    _call("lookup_order", {"order_id": "DF-1002"}, "c1"),
    AIMessage(content="DF-1002 is in transit."),
    _call("retrieve", {"question": "What is your return window?"}, "c2"),
    AIMessage(content="The return window is 30 days."),
    _call("retrieve", {"question": "Can I return an unused lamp for a refund?"}, "c3"),
    AIMessage(content="Yes, unused items can be returned within 30 days."),
]


@pytest.fixture
def out(tmp_path, monkeypatch, capsys):
    RT.set_index(build_faiss_index(docs=load_knowledge_base(roots=(WIKI_DIR,)), index_dir=tmp_path, embeddings=HashingEmbeddings()))
    monkeypatch.setattr(config, "get_chat_model", lambda **k: ScriptedToolChatModel(script=list(SCRIPT)))
    try:
        runpy.run_path(str(LAB), run_name="__main__")
    finally:
        RT.reset_index()
    return capsys.readouterr().out.splitlines()


def test_three_tickets_walk_the_same_loop(out):
    assert "desk_nodes ['__start__', 'model', 'tools', 'ToolCallLimitMiddleware.after_model', '__end__']" in out
    assert [line.split()[1] for line in out if line.startswith("ticket ")] == ["T-3002", "T-3003", "T-3001"]
    assert [line for line in out if line.startswith("road ")] == [LOOP, LOOP, LOOP]
    assert [line for line in out if line.startswith("tools_called ")] == [
        """tools_called ['lookup_order {"order_id": "DF-1002"}']""",
        """tools_called ['retrieve {"question": "What is your return window?"}']""",
        """tools_called ['retrieve {"question": "Can I return an unused lamp for a refund?"}']""",
    ]
    assert "reply DF-1002 is in transit." in out
    assert "same_nodes_for_every_ticket True" in out
    assert "refund_node_on_this_desk False" in out


def test_the_graph_desk_has_roads_and_a_refund_node(out):
    for edge in ("\t__start__ --> classify;", "\tclassify -.-> lookup;", "\tclassify -.-> policy;", "\tclassify -.-> refund;", "\trefund --> __end__;"):
        assert edge in out
    assert out[-1] == "refund_node_on_the_graph_desk True"
