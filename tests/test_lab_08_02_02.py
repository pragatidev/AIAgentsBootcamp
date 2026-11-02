"""Lab 08.02.02 (23.2), build_faiss_index typed by the student. A hashing embedder stands in for the real one here, and only here."""

import importlib
import runpy
from pathlib import Path

import pytest

import config
from dataflow.rag import faiss_index as M
from dataflow.rag.load import KB_DIR, WIKI_DIR, load_knowledge_base
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.fixtures.lab_copy import lab_copy

RT = importlib.import_module("dataflow.tools.retrieve")
LAB = Path(__file__).resolve().parents[1] / "labs" / "08_02_02_index_faiss.py"
ROOTS = (KB_DIR / "customer_facing", KB_DIR / "business_data", WIKI_DIR)


@pytest.fixture
def offline(tmp_path, monkeypatch):
    emb = HashingEmbeddings()
    monkeypatch.setattr(config, "get_embeddings", lambda: emb)
    monkeypatch.setattr(M, "get_embeddings", lambda: emb)
    monkeypatch.setattr(RT, "SCOPE_DIRS", {"customer": tmp_path / "customer", "all": tmp_path / "all"})
    monkeypatch.setattr(M, "INDEX_DIR", tmp_path / "faiss_index")
    RT.reset_index()
    real = M.ROOT / "dataflow" / "data" / "faiss_index"
    before = sorted(p.name for p in real.iterdir()) if real.exists() else None
    yield tmp_path
    RT.reset_index()
    assert (sorted(p.name for p in real.iterdir()) if real.exists() else None) == before


def test_the_run_prints_the_checks(offline, capsys, monkeypatch):
    monkeypatch.setattr(M, "INDEX_DIR", offline / "faiss_index")
    lab = runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "embedder HashingEmbeddings None" in out
    assert "same_width True" in out and "index_dimension 256" in out
    top_source = next(line.split(" ", 1)[1] for line in out if line.startswith("top_source "))
    top_folder = next(line.split(" ", 1)[1] for line in out if line.startswith("top_folder "))
    assert top_source.startswith("dataflow/") and top_folder in {"customer_facing", "business_data", "wiki"}
    assert "desk_index_folders ['dataflow/knowledge_base/customer_facing', 'dataflow/wiki']" in out
    assert lab["LAB_INDEX_DIR"].name == "faiss_index_lab"


def test_typed_build_matches_the_module(offline):
    lab = runpy.run_path(str(LAB), run_name="lab_08_02_02")
    emb = HashingEmbeddings()
    mine = lab["build_faiss_index"](load_knowledge_base(roots=ROOTS), embeddings=emb)
    theirs = M.build_faiss_index(docs=load_knowledge_base(roots=ROOTS), index_dir=None, embeddings=emb)
    assert mine.index.ntotal == theirs.index.ntotal

    def rows(index):
        span = {"start_index", "line_start", "line_end"}
        docs = [index.docstore.search(index.index_to_docstore_id[i]) for i in range(index.index.ntotal)]
        return [(d.page_content, {k: v for k, v in d.metadata.items() if k not in span}) for d in docs]

    assert rows(mine) == rows(theirs)


def test_the_break_loses_where_the_text_came_from(offline, tmp_path, capsys, monkeypatch):
    broken = lab_copy(
        LAB,
        tmp_path,
        "    index = FAISS.from_documents(chunks, embeddings)\n",
        "    index = FAISS.from_texts([chunk.page_content for chunk in chunks], embeddings)\n",
    )
    runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "top_source " in out
    assert "top_row None" in out and "top_folder None" in out
