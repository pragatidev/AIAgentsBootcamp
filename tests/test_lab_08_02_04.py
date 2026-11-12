"""Lab 08.02.04 (23.4), check_dimension typed by the student. Never starts Docker: subprocess, Postgres and the store
are stood in for here, and only here, with a hashing embedder and a scripted tool model."""

import importlib
import math
import runpy
import subprocess
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from dataflow.rag import pgvector_store as PG
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.fixtures.lab_copy import lab_copy

RT = importlib.import_module("dataflow.tools.retrieve")
LAB = Path(__file__).resolve().parents[1] / "labs" / "08_02_04_pgvector.py"


class FakeStore:
    """Rows in memory, cosine distance, the folder filter applied, a wrong width refused like the database."""

    def __init__(self, emb):
        self.emb, self.rows = emb, {}

    def add_documents(self, docs, ids=None):
        for doc, cid in zip(docs, ids):
            self.rows[cid] = (doc, self.emb.embed_query(doc.page_content))
        return list(ids)

    def add_embeddings(self, texts, embeddings, metadatas=None):
        if len(embeddings[0]) != self.emb.dim:
            raise ValueError(f"expected {self.emb.dim} dimensions, not {len(embeddings[0])}")

    def similarity_search_with_score(self, question, k=4, filter=None):
        q = self.emb.embed_query(question)
        allowed = (filter or {}).get("folder", {}).get("$in")
        scored = [
            (doc, 1 - sum(a * b for a, b in zip(q, vec)) / (math.sqrt(sum(a * a for a in vec)) or 1))
            for doc, vec in self.rows.values()
            if allowed is None or doc.metadata.get("folder") in allowed
        ]
        return sorted(scored, key=lambda pair: pair[1])[:k]


@pytest.fixture
def offline(monkeypatch):
    emb = HashingEmbeddings()
    monkeypatch.setattr(config, "get_embeddings", lambda: emb)
    yield emb
    RT.set_pg_store(None)


def _docker(monkeypatch, code):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, code, "", "docker not started by pytest"))


def test_width_check_runs_before_docker(offline, monkeypatch, capsys):
    _docker(monkeypatch, 1)
    with pytest.raises(SystemExit):
        runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "embedder HashingEmbeddings None" in out
    assert "width_check column none -> 256" in out
    assert "width_check column 257 -> refused: embedder dimension 256 does not match column width 257" in out
    assert "BLOCKED ON DOCKER" in out


def test_typed_check_matches_the_module(offline):
    # The two cells before docker compose: the imports and the typed check, which need no Docker.
    first_cells = LAB.read_text(encoding="utf-8").split("# %%\n# Start the course's Postgres")[0]
    namespace = {"__file__": str(LAB)}
    exec(compile(first_cells, str(LAB), "exec"), namespace)
    check = namespace["check_dimension"]
    assert check(offline) == PG.check_dimension(offline) == 256
    for fn in (check, PG.check_dimension):
        with pytest.raises(ValueError, match="embedder dimension 256 does not match column width 257"):
            fn(offline, 257)


def test_the_live_path_answers_from_postgres(offline, monkeypatch, capsys):
    _docker(monkeypatch, 0)
    monkeypatch.setattr(PG, "wait_for_postgres", lambda *a, **k: True)
    monkeypatch.setattr(PG, "column_width", lambda *a, **k: None)
    monkeypatch.setattr(PG, "build_pgvector_store", lambda name, **k: FakeStore(offline))
    call = AIMessage(content="", tool_calls=[{"name": "retrieve", "args": {"question": "customer return window"}, "id": "c1", "type": "tool_call"}])
    reply = AIMessage(content="Returns are allowed within 30 days of delivery when the item is unused.")
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeToolModel(script=[call, reply]))
    lab = runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "compose_returncode 0" in out and "column none yet" in out
    assert any(line.startswith("inserted ") and int(line.split()[1]) > 30 for line in out)
    assert any(line.startswith("refund_on_top ") for line in out)
    assert "wrong_width_error ValueError: expected 256 dimensions, not 257" in out
    assert "tool_calls [('retrieve', {'question': 'customer return window'})]" in out
    sources = next(line for line in out if line.startswith("passages_from_postgres "))
    assert "internal_operations" not in sources and "dataflow/" in sources
    assert "Returns are allowed within 30 days of delivery when the item is unused." in out
    cited = out[out.index("Sources:") + 1 :]
    assert cited and all(line.startswith("dataflow/") for line in cited)
    assert {row["folder"] for row in lab["passages"]} <= {"customer_facing", "wiki"}


def test_the_lab_imports_no_graph():
    from tests.fixtures.lab_imports import graph_imports

    assert graph_imports(LAB) == []


def test_the_break_lets_a_wrong_width_through(offline, monkeypatch, tmp_path, capsys):
    _docker(monkeypatch, 1)
    broken = lab_copy(
        LAB,
        tmp_path,
        '    if expected is not None and width != expected:\n        raise ValueError(f"embedder dimension {width} does not match column width {expected}")\n',
        "",
    )
    with pytest.raises(SystemExit):
        runpy.run_path(str(broken), run_name="__main__")
    assert "width_check column 257 -> 256" in capsys.readouterr().out.splitlines()
