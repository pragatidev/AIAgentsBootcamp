"""Lab 06.06.05 (13.5), fork_before and original_trail_intact typed by the student. One fixture model drives both
desks: RouteDecision says policy for the memory desk, the refund desk's HitlDecision gets route refund, and speak
answers "first answer", then "fork answer"."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs.v3_memory import build_v3_memory
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_06_05_fork.py"
PICK = "    before = next(snapshot for snapshot in history if snapshot.next == (node,))\n"
EDITED = "The return window is 30 days and the lamp qualifies."
QUESTION = "Approve this refund of 49.0 on order DF-1001?"


@pytest.fixture
def scripted(monkeypatch, tmp_path):
    def model(**kwargs):
        return FakeChatModel(route="refund", reply=["first answer", "fork answer"],
                             structured={"RouteDecision": {"route": "policy"}})

    monkeypatch.setattr(config, "get_chat_model", model)
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "unused.jsonl"))


def _value(lines, prefix):
    return next(line[len(prefix):] for line in lines if line.startswith(prefix))


def test_fork_reruns_speak_and_the_trail_stays(scripted, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "original_reply first answer" in out
    assert _value(out, "forked_from ").endswith("next ('speak',)")
    assert "fork_reply fork answer" in out
    before, after = _value(out, "history_before ").split(" history_after ")
    assert int(after) > int(before)
    assert "newest_is_fork_tip True" in out
    assert "original_reply_still_on_its_point True" in out
    assert "original_trail_intact True" in out


def test_refund_replay_parks_again_and_pays_once(scripted, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "refund route refund parked True" in out
    assert "approved Refund issued for order DF-1001. Amount: 49.0. rows 1" in out
    assert "replay parked True reply None" in out
    assert f"replay question {QUESTION}" in out
    assert out[-2:] == ["rows_after_replay 1", "thread next ('refund',)"]


def test_typed_fork_matches_the_package_way(scripted):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    graph = build_v3_memory(model=FakeChatModel(route="orders", reply=["one", "two"]))
    thread = {"configurable": {"thread_id": "t"}}
    graph.invoke({"ticket": "Where is order DF-1001?"}, thread)
    history, forked = lab["fork_before"](graph, thread, "speak", {"reply": EDITED})
    assert forked["reply"] == "two"
    assert lab["original_trail_intact"](graph, history) is True
    assert len(list(graph.get_state_history(thread))) == len(history) + 2


def test_break_fork_after_speak_runs_nothing(scripted, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, PICK, "    before = history[0]\n")
    runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert _value(out, "forked_from ").endswith("next ()")
    assert f"fork_reply {EDITED}" in out
    assert "original_trail_intact True" in out
