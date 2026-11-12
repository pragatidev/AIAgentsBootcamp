"""Lab 08.02.06 (23.6), the retrieve tool typed by the student. A scripted tool model and a hashing index stand in
for the real ones here, and only here."""

import importlib
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

import config
from dataflow.rag.faiss_index import build_faiss_index
from dataflow.rag.load import WIKI_DIR, load_knowledge_base
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.fixtures.lab_copy import lab_copy

RT = importlib.import_module("dataflow.tools.retrieve")
LAB = Path(__file__).resolve().parents[1] / "labs" / "08_02_06_bind_retrieve_tool.py"
POLICY = "Can I send back an unused lamp after twelve days?"


def _call(name, args, cid):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid, "type": "tool_call"}])


SCRIPT = [
    _call("retrieve", {"question": POLICY}, "c1"),
    AIMessage(content="Yes, within 30 days of delivery."),
    _call("lookup_order", {"order_id": "DF-1002"}, "c2"),
    AIMessage(content="DF-1002 is in transit."),
    AIMessage(content="You are welcome."),
    _call("retrieve", {"question": POLICY}, "c3"),
    AIMessage(content="Yes, within 30 days of delivery."),
]


@pytest.fixture
def offline(tmp_path, monkeypatch):
    RT.set_index(build_faiss_index(docs=load_knowledge_base(roots=(WIKI_DIR,)), index_dir=tmp_path, embeddings=HashingEmbeddings()))
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeToolModel(script=list(SCRIPT)))
    yield
    RT.reset_index()


def test_four_runs_fire_what_was_called(offline, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    fired = [line for line in out if line.startswith("tools_fired")]
    assert fired == ["tools_fired ['retrieve']", "tools_fired ['lookup_order']", "tools_fired []", "tools_fired ['retrieve']"]
    assert "desk_tools ['lookup_order', 'retrieve']" in out
    assert any(line.startswith("tools passage dataflow/wiki/") for line in out)


def test_typed_tool_is_the_modules_tool_on_the_wire(offline):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    assert convert_to_openai_tool(lab["retrieve"]) == convert_to_openai_tool(RT.retrieve)


def test_the_break_changes_the_wire_description(offline, tmp_path):
    old = '    """Search the DataFlow customer policies and guides (wiki and customer facing pages) for a customer question. Returns passages with their source file."""\n'
    broken = lab_copy(LAB, tmp_path, old, '    """Look up a DataFlow order by its id."""\n')
    lab = runpy.run_path(str(broken), run_name="__main__")
    assert convert_to_openai_tool(lab["retrieve"])["function"]["description"] == "Look up a DataFlow order by its id."


def test_the_desk_is_create_agent_and_the_lab_imports_no_graph(offline, capsys):
    from tests.fixtures.lab_imports import graph_imports

    lab = runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert list(lab["desk"].get_graph().nodes) == ["__start__", "model", "tools", "__end__"]
    assert 'model tool_call retrieve {"question": "Can I send back an unused lamp after twelve days?"}' in out
    assert "model reply Yes, within 30 days of delivery." in out
    assert graph_imports(LAB) == []
