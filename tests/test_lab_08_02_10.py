"""Lab 08.02.10 (23.10), allowed_folders and scoped_folders typed by the student. A scripted tool model and a hashing
index over every folder stand in for the real ones here, and only here."""

import importlib
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from dataflow.graphs.v1_triage import DeskContext
from dataflow.rag.faiss_index import build_faiss_index
from dataflow.rag.load import load_knowledge_base
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.fixtures.lab_copy import lab_copy

RT = importlib.import_module("dataflow.tools.retrieve")
LAB = Path(__file__).resolve().parents[1] / "labs" / "08_02_10_scope_before_search.py"
ASK = "employee handbook return equipment within 30 days of termination"
ENVELOPES = [None, "anon", "desk-lead", "reviewer-1", "reviewer-2", "contractor-7", ""]


def _script():
    call = AIMessage(content="", tool_calls=[{"name": "retrieve", "args": {"question": ASK, "k": 5, "folder": "internal_operations"}, "id": "c", "type": "tool_call"}])
    return [call, AIMessage(content="Done."), call, AIMessage(content="Done."), call, AIMessage(content="Done.")]


@pytest.fixture(scope="module")
def every_folder():
    return build_faiss_index(docs=load_knowledge_base(), index_dir=None, embeddings=HashingEmbeddings())


@pytest.fixture(autouse=True)
def offline(every_folder, monkeypatch):
    RT.set_index(every_folder)
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeToolModel(script=_script()))
    yield
    RT.reset_index()


def _out(path, capsys):
    namespace = runpy.run_path(str(path), run_name="__main__")
    return namespace, capsys.readouterr().out.splitlines()


def _reached(out):
    actor, found = None, {}
    for line in out:
        if line.startswith("actor "):
            actor = line.split()[1]
        elif line.startswith("  handbook_reached "):
            found[actor] = line.endswith("True")
    return found


def test_the_envelope_decides_and_the_models_folder_is_ignored(capsys):
    _, out = _out(LAB, capsys)
    assert "tool_parameters ['k', 'question']" in out
    assert _reached(out) == {"anon": False, "desk-lead": True, "contractor-7": False}
    assert "code_widens anon internal_operations -> {'found': False, 'reason': \"folder internal_operations is outside this caller's scope\"}" in out


@pytest.mark.parametrize("actor", ENVELOPES)
def test_typed_functions_match_the_module(capsys, actor):
    lab, _ = _out(LAB, capsys)
    ctx = None if actor is None else DeskContext(model=None, actor_id=actor)
    assert lab["allowed_folders"](ctx) == RT.allowed_folders(ctx)
    for folder in (None, "wiki", "internal_operations"):
        assert lab["scoped_folders"](ctx, folder) == RT.scoped_folders(ctx, folder)


def test_the_break_hands_an_unknown_actor_the_handbook(tmp_path, capsys):
    broken = lab_copy(LAB, tmp_path, 'ACTOR_SCOPE.get(str(actor), "customer")] if actor', 'ACTOR_SCOPE.get(str(actor), "support_agent")] if actor')
    _, out = _out(broken, capsys)
    assert _reached(out)["contractor-7"] is True


def test_the_desk_is_create_agent_and_the_lab_imports_no_graph(capsys):
    from dataflow.envelope import DeskContext as envelope
    from tests.fixtures.lab_imports import graph_imports

    lab, _ = _out(LAB, capsys)
    assert list(lab["desk"].get_graph().nodes) == ["__start__", "model", "tools", "__end__"]
    assert lab["DeskContext"] is envelope is DeskContext
    assert graph_imports(LAB) == []
