"""Lab 08.03.07 (24.7), reciprocal_rank_fusion typed by the student. A hashing index and a scripted tool model stand
in for the real ones here, and only here. Skips with a reason where rank-bm25 is not installed."""

import importlib
import runpy
from pathlib import Path

import pytest

pytest.importorskip("rank_bm25", reason="rank-bm25 is in requirements.txt; this venv has not installed it")

import config  # noqa: E402
from dataflow.rag.faiss_index import build_faiss_index  # noqa: E402
from dataflow.rag.hybrid import reciprocal_rank_fusion as module_rrf  # noqa: E402
from dataflow.rag.load import KB_DIR, WIKI_DIR, load_knowledge_base  # noqa: E402
from tests.fixtures.fake_model import FakeToolModel  # noqa: E402
from tests.fixtures.hashing_embeddings import HashingEmbeddings  # noqa: E402
from tests.fixtures.lab_copy import lab_copy  # noqa: E402

RT = importlib.import_module("dataflow.tools.retrieve")
LAB = Path(__file__).resolve().parents[1] / "labs" / "08_03_07_hybrid_and_rerank.py"


def _r(name):
    return {"source": f"{name}.md", "row": None, "start_index": 0, "text": name}


LISTS = [[_r("a"), _r("b"), _r("c")], [_r("c"), _r("a"), _r("d")]]


@pytest.fixture(scope="module")
def customer_index():
    return build_faiss_index(docs=load_knowledge_base(roots=(KB_DIR / "customer_facing", WIKI_DIR)), index_dir=None, embeddings=HashingEmbeddings())


@pytest.fixture(autouse=True)
def offline(customer_index, monkeypatch):
    RT.set_index(customer_index)
    from langchain_core.messages import AIMessage  # noqa: E402
    call = AIMessage(content="", tool_calls=[{"name": "retrieve", "args": {"question": "What does the error code mean?"}, "id": "c", "type": "tool_call"}])
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeToolModel(script=[call, AIMessage(content="See the guide."), call, AIMessage(content="See the guide.")]))
    yield
    RT.reset_index()


def _out(path, capsys):
    namespace = runpy.run_path(str(path), run_name="__main__")
    return namespace, capsys.readouterr().out.splitlines()


def test_every_code_probed_and_two_desks(capsys):
    _, out = _out(LAB, capsys)
    assert "codes_in_guide 20" in out
    assert sum(1 for line in out if line.startswith("probe ")) == 20
    assert any(line.startswith("worst_dense_code ") for line in out)
    assert [line for line in out if line.startswith("desk ")] == ["desk dense", "desk hybrid"]
    assert sum(1 for line in out if line.startswith("  tool_call retrieve ")) == 2 and not any(line.startswith("  rerank ") for line in out)


def test_bm25_finds_every_code_in_its_top_ten(capsys):
    # BM25 does not depend on the embedder, so its ranks are the same with the course's embedder.
    _, out = _out(LAB, capsys)
    bm25 = [line.split(" bm25 ")[1].split()[0] for line in out if line.startswith("probe ")]
    assert len(bm25) == 20 and "None" not in bm25


def test_typed_fusion_matches_the_known_answer(capsys):
    lab, _ = _out(LAB, capsys)
    mine, theirs = lab["reciprocal_rank_fusion"](LISTS), module_rrf(LISTS)
    assert [(row["source"], round(row["rrf"], 6)) for row in mine] == [(row["source"], round(row["rrf"], 6)) for row in theirs]
    assert [row["source"] for row in mine] == ["a.md", "c.md", "b.md", "d.md"]
    assert mine[0]["rrf"] == pytest.approx(1 / 61 + 1 / 62)


def test_the_break_loses_the_constant(tmp_path, capsys):
    broken = lab_copy(LAB, tmp_path, "k: int = RRF_K) -> list[dict]:", "k: int = 0) -> list[dict]:")
    lab, _ = _out(broken, capsys)
    fused = lab["reciprocal_rank_fusion"](LISTS)
    assert fused[0]["rrf"] == pytest.approx(1 / 1 + 1 / 2)
    assert fused[0]["rrf"] != pytest.approx(module_rrf(LISTS)[0]["rrf"])


def test_each_desk_searches_in_its_own_mode_and_the_lab_imports_no_graph(monkeypatch, capsys):
    from tests.fixtures.lab_imports import graph_imports

    real, modes = RT.retrieve_passages, []
    monkeypatch.setattr(RT, "retrieve_passages", lambda *a, **k: modes.append(k.get("mode")) or real(*a, **k))
    _, out = _out(LAB, capsys)
    # Per desk: the lab's own search with the customer's words, then the desk's retrieve tool.
    assert modes == ["dense", "dense", "hybrid", "hybrid"]
    assert sum(1 for line in out if line.startswith("  search_rank_of_code_chunk ")) == 2
    assert sum(1 for line in out if line.startswith("  model_calls 2 tokens ")) == 2
    assert graph_imports(LAB) == []
