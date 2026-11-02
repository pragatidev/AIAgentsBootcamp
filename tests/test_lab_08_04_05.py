"""Lab 08.04.05 (25.5), refusal_scores typed by the student. A scripted model, a scripted judge and a hashing index
stand in for the real ones here, and only here."""

import importlib
import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs.rag_graph import REFUSE_TEMPLATE
from dataflow.rag.faiss_index import build_faiss_index
from dataflow.rag.load import load_knowledge_base
from eval.runners import rag_metrics as M
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.fixtures.lab_copy import lab_copy

RT = importlib.import_module("dataflow.tools.retrieve")
LAB = Path(__file__).resolve().parents[1] / "labs" / "08_04_05_rag_evals.py"
HOUSE = REFUSE_TEMPLATE.format(q="x")


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    return build_faiss_index(docs=load_knowledge_base(), index_dir=tmp_path_factory.mktemp("all"), embeddings=HashingEmbeddings())


@pytest.fixture(autouse=True)
def offline(index, monkeypatch):
    RT.set_index(index)
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="retrieve", reply="1"))
    yield
    RT.reset_index()


class Judge:
    def __init__(self):
        self.calls = 0

    def __call__(self, answer, passages, model=None):
        self.calls += 1
        return 0 if "lifetime warranty" in answer else 1


def _out(path, capsys):
    runpy.run_path(str(path), run_name="__main__")
    return capsys.readouterr().out.splitlines()


@pytest.mark.parametrize(
    "kind, answer, expected, calls",
    [
        ("refuse", HOUSE, {"refused": True, "refused_correctly": 1, "faithfulness": 1, "fluent_miss": False, "over_refusal": False}, 0),
        ("refuse", "Yes, every desk lamp has a lifetime warranty.", {"refused": False, "refused_correctly": 0, "faithfulness": 0, "fluent_miss": True, "over_refusal": False}, 1),
        ("refuse", "I don't have information about a lifetime warranty.", {"refused": False, "refused_correctly": 0, "faithfulness": 0, "fluent_miss": True, "over_refusal": False}, 1),
        ("policy", HOUSE, {"refused": True, "refused_correctly": 0, "faithfulness": 1, "fluent_miss": False, "over_refusal": True}, 0),
        ("policy", "Returns are allowed within 30 days.", {"refused": False, "refused_correctly": 0, "faithfulness": 1, "fluent_miss": False, "over_refusal": False}, 1),
    ],
)
@pytest.mark.parametrize("which", ["lab", "module"])
def test_refusal_scores_both_copies(which, kind, answer, expected, calls):
    fn = runpy.run_path(str(LAB), run_name="lab_08_04_05")["refusal_scores"] if which == "lab" else M.refusal_scores
    judge = Judge()
    assert fn(kind, answer, [], judge=judge) == expected
    assert judge.calls == calls


def test_the_run_prints_the_table_and_the_checks(capsys):
    out = _out(LAB, capsys)
    assert any(line.startswith("pipeline  faithfulness") and line.endswith("tokens_per_q  calls_per_q") for line in out)
    assert sum(1 for line in out if line.startswith("naive_answer refuse-")) == 3
    assert "recall_by_definition 5 of 12" in out
    assert sum(1 for line in out if line.startswith("refusal_scores ")) == 5
    assert "judge_is_desk_model True" in out
    assert any(line.startswith("over_refusals naive") for line in out)


def test_the_break_flags_a_refusal_on_a_policy_row(tmp_path, capsys):
    broken = lab_copy(LAB, tmp_path, '        "fluent_miss": kind == "refuse" and not refused and bool(answer.strip()),\n', '        "fluent_miss": not refused and bool(answer.strip()),\n')
    lab = runpy.run_path(str(broken), run_name="lab_08_04_05")
    assert lab["refusal_scores"]("policy", "Returns are allowed within 30 days.", [], judge=Judge())["fluent_miss"] is True
