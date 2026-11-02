"""Hybrid search and rerank (24.7). Hand-ranked lists, the real troubleshooting guide, a scripted model here only. No Ollama."""

import importlib
import inspect

import pytest

import config
from dataflow.graphs.rag_graph import build_rag_graph, rerank
from dataflow.rag.chunk import chunk_by_heading
from dataflow.rag.hybrid import reciprocal_rank_fusion, tokenize
from dataflow.rag.load import KB_DIR, load_knowledge_base
from tests.fixtures.fake_model import FakeChatModel

RT = importlib.import_module("dataflow.tools.retrieve")
GUIDE = KB_DIR / "customer_facing" / "troubleshooting_guide.txt"


def _r(name):
    return {"source": f"{name}.md", "row": None, "start_index": 0, "text": name}


def test_rrf_known_answer():
    dense = [_r("a"), _r("b"), _r("c")]
    keyword = [_r("c"), _r("a"), _r("d")]
    fused = reciprocal_rank_fusion([dense, keyword], k=60)
    assert [row["source"] for row in fused] == ["a.md", "c.md", "b.md", "d.md"]
    assert fused[0]["rrf"] == pytest.approx(1 / 61 + 1 / 62)
    assert fused[1]["rrf"] == pytest.approx(1 / 63 + 1 / 61)
    assert fused[2]["rrf"] == pytest.approx(1 / 62)
    assert fused[3]["rrf"] == pytest.approx(1 / 63)


def test_rrf_dedupes_same_chunk():
    same = {"source": "x.txt", "row": None, "start_index": 120, "text": "Error Code: PERM-5005"}
    fused = reciprocal_rank_fusion([[same], [dict(same, score=7.5)]])
    assert len(fused) == 1 and fused[0]["rrf"] == pytest.approx(2 / 61)


def test_tokenize_keeps_codes_whole():
    assert tokenize("What does error PERM-5005 mean?") == ["what", "does", "error", "perm-5005", "mean"]


def test_bm25_ranks_exact_code_first():
    pytest.importorskip("rank_bm25", reason="rank-bm25 is in requirements.txt; this venv has not installed it")
    from dataflow.rag.hybrid import bm25_rows, build_bm25

    chunks = chunk_by_heading(load_knowledge_base(roots=(GUIDE,)))
    top = bm25_rows(build_bm25(chunks), "PERM-5005", k=1)[0]
    assert "Error Code: PERM-5005" in top["text"]


def test_hybrid_through_retrieve_passages(tmp_path):
    pytest.importorskip("rank_bm25", reason="rank-bm25 is in requirements.txt; this venv has not installed it")
    from dataflow.rag.faiss_index import build_faiss_index
    from tests.fixtures.hashing_embeddings import HashingEmbeddings

    RT.set_index(build_faiss_index(docs=load_knowledge_base(roots=(KB_DIR / "customer_facing",)), index_dir=tmp_path, embeddings=HashingEmbeddings()))
    try:
        rows = RT.retrieve_passages("What does error SSO-9001 mean and how do I fix it?", k=3, mode="hybrid")
        assert any("Error Code: SSO-9001" in row["text"] for row in rows)
        assert all("rrf" in row for row in rows)
    finally:
        RT.reset_index()


def test_rerank_orders_by_model_score():
    passages = [{"source": "a.md", "text": "a"}, {"source": "b.md", "text": "b"}, {"source": "c.md", "text": "c"}]
    fake = FakeChatModel(structured={"Relevance": [{"score": 1, "reason": "x"}, {"score": 3, "reason": "y"}, {"score": 1, "reason": "z"}]})
    out = rerank({"question": "q", "passages": passages}, model=fake, keep=2)
    assert [p["source"] for p in out["passages"]] == ["b.md", "a.md"]
    assert [r["was"] for r in out["reranked"]] == [1, 0, 2]


def test_hybrid_and_rerank_are_off_by_default():
    assert config.RETRIEVE_MODE == "dense"
    params = inspect.signature(build_rag_graph).parameters
    assert params["rerank_enabled"].default is False and params["retrieve_mode"].default is None
    nodes = set(build_rag_graph(model=FakeChatModel(route="answer")).get_graph().nodes)
    assert "rerank" not in nodes
    nodes = set(build_rag_graph(model=FakeChatModel(route="answer"), rerank_enabled=True).get_graph().nodes)
    assert "rerank" in nodes


def test_the_graph_reranks_a_shortlist(monkeypatch):
    seen = {}

    def shortlist(question, k=3, folder=None, *, scope="customer", store=None, mode=None):
        seen["k"], seen["mode"] = k, mode
        return [{"source": f"{n}.md", "text": n, "folder": "wiki"} for n in "abcdefghij"[:k]]

    monkeypatch.setattr("dataflow.graphs.rag_graph.retrieve_passages", shortlist)
    scores = [{"score": 0, "reason": "-"}] * 9 + [{"score": 3, "reason": "the answer"}]
    fake = FakeChatModel(route="retrieve", reply="An answer.", structured={"Relevance": scores, "Grade": {"label": "keep", "reason": "k"}})
    out = build_rag_graph(model=fake, rerank_enabled=True, retrieve_mode="hybrid").invoke({"question": "q"})
    assert seen == {"k": 10, "mode": "hybrid"}
    assert out["passages"][0]["source"] == "j.md" and len(out["passages"]) == 3
