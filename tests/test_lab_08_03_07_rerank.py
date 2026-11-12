"""Lab 08.03.07, second file (24.7): the rerank on the DataFlow graph. A hashing index and a scripted model stand in
for the real ones here, and only here. Skips with a reason where rank-bm25 is not installed."""

import importlib
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

pytest.importorskip("rank_bm25", reason="rank-bm25 is in requirements.txt; this venv has not installed it")

import config  # noqa: E402
from dataflow.rag.faiss_index import build_faiss_index  # noqa: E402
from dataflow.rag.load import KB_DIR, WIKI_DIR, load_knowledge_base  # noqa: E402
from tests.fixtures.fake_model import FakeChatModel, FakeToolModel  # noqa: E402
from tests.fixtures.hashing_embeddings import HashingEmbeddings  # noqa: E402
from tests.fixtures.lab_imports import graph_imports  # noqa: E402

RT = importlib.import_module("dataflow.tools.retrieve")
LABS = Path(__file__).resolve().parents[1] / "labs"
LAB = LABS / "08_03_07_rerank_on_the_graph.py"
FIRST = LABS / "08_03_07_hybrid_and_rerank.py"


@pytest.fixture(scope="module")
def customer_index():
    return build_faiss_index(docs=load_knowledge_base(roots=(KB_DIR / "customer_facing", WIKI_DIR)), index_dir=None, embeddings=HashingEmbeddings())


@pytest.fixture(autouse=True)
def offline(customer_index, monkeypatch):
    RT.set_index(customer_index)
    scores = [{"score": 1, "reason": "related"}] * 9 + [{"score": 3, "reason": "names the code"}]
    model = FakeChatModel(route="retrieve", reply="See the guide.", structured={"Relevance": scores, "Grade": {"label": "keep", "reason": "k"}})
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    yield
    RT.reset_index()


def _out(path, capsys):
    runpy.run_path(str(path), run_name="__main__")
    return capsys.readouterr().out.splitlines()


def test_two_graph_desks_and_the_rerank_scores_a_shortlist_of_ten(capsys):
    out = _out(LAB, capsys)
    assert [line for line in out if line.startswith("desk ")] == ["desk hybrid", "desk hybrid_rerank"]
    rerank = [line for line in out if line.startswith("  rerank ")]
    assert len(rerank) == 10 and out.index(rerank[0]) > out.index("desk hybrid_rerank")
    assert sum(1 for line in out if line.startswith("  model_calls ")) == 2


def test_it_picks_the_same_code_as_the_first_file(monkeypatch, capsys):
    second = next(line for line in _out(LAB, capsys) if line.startswith("worst_dense_code "))
    call = AIMessage(content="", tool_calls=[{"name": "retrieve", "args": {"question": "What does the error code mean?"}, "id": "c", "type": "tool_call"}])
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeToolModel(script=[call, AIMessage(content="See the guide."), call, AIMessage(content="See the guide.")]))
    first = next(line for line in _out(FIRST, capsys) if line.startswith("worst_dense_code "))
    assert first.startswith(second + " bm25 ")


def test_the_graph_import_lives_in_this_file_only():
    assert graph_imports(LAB) == ["dataflow.graphs.rag_graph", "eval.runners.rag_metrics"]
    assert graph_imports(FIRST) == []
