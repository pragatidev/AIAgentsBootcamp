"""Lab 06.07.04 (16.4), ParentState, fan_out and score typed by the student over the TalentFlow pile; the gather
broken by taking operator.add off scores. The fixture model scores every resume 80 and writes the summary."""

import runpy
from pathlib import Path
from typing import get_type_hints

import pytest
from langgraph.errors import InvalidUpdateError

import config
from talentflow.graphs import score_resumes
from talentflow.graphs.score_resumes import ParentState, build_score_resumes, load_resumes
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_07_04_map_reduce_resumes.py"
REDUCER = "    scores: Annotated[list, operator.add]\n"
SUMMARY = "Alex Thompson and Sarah Chen are the top two. The rest are possible. Hire from the top of the table."


@pytest.fixture
def fixture_model(monkeypatch):
    model = FakeChatModel(reply=SUMMARY)
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    monkeypatch.setattr(score_resumes, "get_chat_model", lambda **k: model)
    return model


def _names() -> list[str]:
    return [row["name"] for row in load_resumes()["resumes"]]


def test_lab_scores_the_whole_pile(fixture_model, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "model FakeChatModel None"
    assert out[1] == "langchain-core 1.6.2" and out[2] == "langgraph 1.2.11"
    assert "resumes_loaded 10 sends 10" in out
    assert any(line.startswith("one_packet node score keys ['job', 'name', 'text'] name ") for line in out)
    assert f"gathered_order {_names()}" in out
    assert "same_order_as_sends True" in out
    assert out[out.index("ranking") + 1] == "name\tscore\tfit"
    assert SUMMARY in out
    steps = out[out.index("history_oldest_first 5") + 1 :]
    assert steps == [
        "step -1 next {'__start__': 1}",
        "step 0 next {'load': 1}",
        "step 1 next {'score': 10}",
        "step 2 next {'summarize': 1}",
        "step 3 next {}",
    ]
    assert fixture_model.calls == 11


def test_typed_pieces_match_the_package(fixture_model):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    assert get_type_hints(lab["ParentState"], include_extras=True) == get_type_hints(ParentState, include_extras=True)
    loaded = load_resumes()
    mine, package = lab["fan_out"](loaded), score_resumes.fan_out(loaded)
    assert [(s.node, s.arg) for s in mine] == [(s.node, s.arg) for s in package]
    assert lab["score"](mine[0].arg) == score_resumes.score(package[0].arg)
    thread = {"configurable": {"thread_id": "test-16-4"}}
    assert lab["build_map_reduce"]().invoke({}, thread)["scores"] == build_score_resumes(model=fixture_model).invoke(
        {}, thread
    )["scores"]


def test_break_no_reducer_raises_after_every_copy_ran(fixture_model, tmp_path):
    broken = lab_copy_dataflow(LAB, tmp_path, REDUCER, "    scores: list\n")
    with pytest.raises(InvalidUpdateError) as caught:
        runpy.run_path(str(broken), run_name="__main__")
    assert str(caught.value).splitlines()[0] == (
        "At key 'scores': Can receive only one value per step. Use an Annotated key to handle multiple values."
    )
    assert fixture_model.calls == 10
