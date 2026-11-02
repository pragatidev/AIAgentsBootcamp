"""Lab 08.04.08 (25.8), retrieval_metrics typed by the student. A hashing index stands in for the real one here, and
only here; no chat model is ever called."""

import importlib
import runpy
from pathlib import Path

import pytest

import config
from dataflow.rag.faiss_index import build_faiss_index
from dataflow.rag.load import load_knowledge_base
from eval.runners import rag_metrics as M
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.fixtures.lab_copy import lab_copy

RT = importlib.import_module("dataflow.tools.retrieve")
LAB = Path(__file__).resolve().parents[1] / "labs" / "08_04_08_retrieval_metrics.py"


@pytest.fixture(scope="module")
def every_folder():
    return build_faiss_index(docs=load_knowledge_base(), index_dir=None, embeddings=HashingEmbeddings())


@pytest.fixture(autouse=True)
def offline(every_folder, monkeypatch):
    RT.set_index(every_folder)
    monkeypatch.setattr(config, "get_embeddings", lambda: HashingEmbeddings())

    def no_model(**kwargs):
        raise AssertionError("the retrieval lab called a chat model")

    monkeypatch.setattr(config, "get_chat_model", no_model)
    yield
    RT.reset_index()


def _out(path, capsys):
    namespace = runpy.run_path(str(path), run_name="__main__")
    return namespace, capsys.readouterr().out.splitlines()


def test_seven_rows_scored_five_left_out(capsys):
    _, out = _out(LAB, capsys)
    assert sum(1 for line in out if line.startswith("dense ") and " rank " in line) == 7
    assert "dense rows_left_out 5" in out
    assert "context_recall_by_definition 5 of 12" in out
    assert "one_scored_row_moves_a_mean_by 0.143" in out


@pytest.mark.parametrize("row_id", ["policy-return", "refuse-coffee", "paraphrase-p0", "lookup-1001"])
def test_typed_metrics_match_the_module(capsys, row_id):
    lab, _ = _out(LAB, capsys)
    row = {r["id"]: r for r in M.load_questions()}[row_id]
    passages = [{"source": "dataflow/wiki/shipping.md"}, {"source": str(row.get("expected_source") or "x")}, {"source": "y"}]
    assert lab["retrieval_metrics"](row, passages) == M.retrieval_metrics(row, passages)


def test_the_break_inflates_the_means(tmp_path, capsys):
    perfect = '        return {"id": row.get("id"), "rank": 0, "recall_at_1": 1, "recall_at_3": 1, "recall_at_5": 1, "mrr": 1.0}\n'
    _, out = _out(lab_copy(LAB, tmp_path, "        return None\n", perfect), capsys)
    assert "dense rows_left_out 0" in out
