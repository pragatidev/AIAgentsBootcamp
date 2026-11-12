"""The DataFlow desk on create_agent (dataflow/rag/desk.py) and the passages read out of its tool messages.

A scripted tool model and a hashing index over every folder stand in for the real ones here, and only here.
"""

import importlib
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from dataflow.envelope import DeskContext
from dataflow.rag import desk as DESK
from dataflow.rag.cite import format_sources, tool_passages
from dataflow.rag.faiss_index import build_faiss_index
from dataflow.rag.load import load_knowledge_base
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.fixtures.lab_imports import graph_imports

RT = importlib.import_module("dataflow.tools.retrieve")
ROOT = Path(__file__).resolve().parents[1]
ASK = "employee handbook return equipment within 30 days of termination"


def _call(name="retrieve", args=None, cid="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {"question": ASK, "k": 5}, "id": cid, "type": "tool_call"}])


@pytest.fixture(scope="module")
def every_folder():
    return build_faiss_index(docs=load_knowledge_base(), index_dir=None, embeddings=HashingEmbeddings())


@pytest.fixture
def indexed(every_folder):
    RT.set_index(every_folder)
    yield
    RT.reset_index()


def test_the_desk_modules_import_no_graph():
    for name in ("dataflow/rag/desk.py", "dataflow/rag/cite.py", "dataflow/envelope.py"):
        assert graph_imports(ROOT / name) == [], name


def test_the_system_prompt_is_the_tool_cycles_word_for_word():
    from dataflow.graphs.rag_tool_cycle import AGENT_SYSTEM, DESK_TOOLS

    assert DESK.DESK_SYSTEM == AGENT_SYSTEM
    assert [t.name for t in DESK_TOOLS] == ["lookup_order", "retrieve"]


def test_it_is_create_agent_with_the_envelope_and_one_guard():
    desk = DESK.build_rag_desk(model=FakeToolModel(script=[AIMessage(content="Hello.")]))
    assert list(desk.get_graph().nodes) == ["__start__", "model", "tools", "ToolCallLimitMiddleware.after_model", "__end__"]
    assert desk.builder.context_schema is DeskContext
    bare = DESK.build_rag_desk(model=FakeToolModel(script=[AIMessage(content="Hello.")]), middleware=[])
    assert list(bare.get_graph().nodes) == ["__start__", "model", "tools", "__end__"]


@pytest.mark.parametrize("actor, reached", [("anon", False), ("contractor-7", False), ("desk-lead", True)])
def test_the_envelope_sets_the_scope(indexed, actor, reached):
    desk = DESK.build_rag_desk(model=FakeToolModel(script=[_call(), AIMessage(content="Done.")]))
    state = DESK.ask_desk(desk, "Do I have to return company equipment?", actor_id=actor)
    rows = tool_passages(state["messages"])
    assert rows and DESK.reply_text(state) == "Done."
    assert any("employee_handbook" in row["source"] for row in rows) is reached
    assert {row["folder"] for row in rows} <= RT.SCOPES[RT.ACTOR_SCOPE.get(actor, "customer")]


def test_a_model_that_keeps_calling_is_stopped_by_the_limit(indexed):
    desk = DESK.build_rag_desk(model=FakeToolModel(script=[_call(cid=f"c{n}") for n in range(12)]))
    state = DESK.ask_desk(desk, "Do I have to return company equipment?")
    ran = [m for m in state["messages"] if m.type == "tool" and getattr(m, "status", "success") != "error"]
    assert len(ran) == DESK.TOOL_RUN_LIMIT
    assert DESK.reply_text(state) == f"Tool call limit reached: run limit exceeded ({DESK.TOOL_RUN_LIMIT + 1}/{DESK.TOOL_RUN_LIMIT} calls)."


def test_store_and_mode_are_the_deployments_never_the_models(monkeypatch):
    assert DESK.retrieve_tool() is RT.retrieve
    seen = []
    monkeypatch.setattr(RT, "retrieve_passages", lambda question, **kwargs: seen.append(kwargs) or [{"source": "dataflow/wiki/return_policy.md", "folder": "wiki"}])
    for kwargs in ({"mode": "hybrid"}, {"store": "pgvector"}):
        fixed = DESK.retrieve_tool(**kwargs)
        assert convert_to_openai_tool(fixed) == convert_to_openai_tool(RT.retrieve)
        desk = DESK.build_rag_desk(model=FakeToolModel(script=[_call(), AIMessage(content="Done.")]), **kwargs)
        state = DESK.ask_desk(desk, "anything", actor_id="desk-lead")
        assert tool_passages(state["messages"]) == [{"source": "dataflow/wiki/return_policy.md", "folder": "wiki"}]
    assert seen == [
        {"k": 5, "scope": "support_agent", "store": None, "mode": "hybrid"},
        {"k": 5, "scope": "support_agent", "store": "pgvector", "mode": None},
    ]


def test_tool_passages_reads_retrieve_rows_once_and_nothing_else():
    row = {"source": "dataflow/wiki/return_policy.md", "heading_path": "DataFlow return policy", "row": None, "line_start": 1, "line_end": 9}
    csv = {"source": "dataflow/knowledge_base/business_data/billing_and_pricing.csv", "row": 0}
    messages = [
        HumanMessage(content="hi"),
        _call(),
        ToolMessage(content='[%s, %s]' % (__import__("json").dumps(row), __import__("json").dumps(csv)), name="retrieve", tool_call_id="c1"),
        ToolMessage(content='{"found": true, "order_id": "DF-1002"}', name="lookup_order", tool_call_id="c2"),
        ToolMessage(content='{"found": false, "reason": "folder x is outside this caller\'s scope"}', name="retrieve", tool_call_id="c3"),
        ToolMessage(content="not json", name="retrieve", tool_call_id="c4"),
        ToolMessage(content='[%s]' % __import__("json").dumps(row), name="retrieve", tool_call_id="c5"),
        AIMessage(content="Thirty days."),
    ]
    assert tool_passages(messages) == [row, csv]
    assert tool_passages([]) == [] and tool_passages(None) == []
    assert format_sources(tool_passages(messages)).splitlines() == [
        "dataflow/wiki/return_policy.md > DataFlow return policy lines 1 to 9",
        "dataflow/knowledge_base/business_data/billing_and_pricing.csv row 0",
    ]
