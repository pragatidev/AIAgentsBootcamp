"""Lab 03.03, measure typed by the student, on a known trace and with no trace at all. No model."""

import json
import runpy
from pathlib import Path

import pytest

from dataflow.context import rot
from dataflow.context.agent import count_tokens

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_03_measure_tokens.py"


def known_trace() -> dict:
    messages = [{"role": "system", "content": "desk"}]
    trace = []
    for turn in range(1, 6):
        messages.append({"role": "user", "content": f"question {turn} " + "word " * 30})
        trace.append({"turn": turn, "tokens": count_tokens(messages), "usage": {"input_tokens": 40 * turn}})
        messages.append({"role": "assistant", "content": "answer " * 20})
    return {
        "window": 120,
        "constraint_turn": 2,
        "probe_turn": 5,
        "runs": {
            "A": {"window": None, "trace": trace, "messages": messages},
            "B": {"window": 120, "trace": trace, "messages": messages},
        },
    }


@pytest.fixture
def written(tmp_path, monkeypatch):
    path = tmp_path / "_last_rot.json"
    path.write_text(json.dumps(known_trace()), encoding="utf-8")
    monkeypatch.setattr(rot, "ROT_TRACE", path)
    return path


def test_measure_matches_count_tokens(written):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    messages = known_trace()["runs"]["A"]["messages"]
    for k in range(1, 6):
        assert lab["measure"](messages[: 2 * k]) == count_tokens(messages[: 2 * k])


def test_both_counts_and_the_cut(written, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    trace = known_trace()["runs"]["A"]["trace"]
    assert f"rule turn 2 library_tokens {trace[1]['tokens']} server_input_tokens 80" in out
    assert f"probe turn 5 library_tokens {trace[4]['tokens']} server_input_tokens 200" in out
    assert [line for line in out if line.startswith("cut_by_server")] == ["cut_by_server False", "cut_by_server False"]


def test_the_cut_shows_when_the_server_read_less_than_the_window(tmp_path, monkeypatch, capsys):
    data = known_trace()
    data["runs"]["B"]["trace"] = [dict(row, usage={"input_tokens": 110}) for row in data["runs"]["B"]["trace"]]
    path = tmp_path / "_last_rot.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(rot, "ROT_TRACE", path)
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert [line for line in out if line.startswith("cut_by_server")] == ["cut_by_server False", "cut_by_server True"]


def test_missing_trace_says_run_the_long_run_first(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rot, "ROT_TRACE", tmp_path / "absent.json")
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(str(LAB), run_name="__main__")
    assert stop.value.code == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("missing_rot_trace ")
    assert out[1] == "run labs/03_02_context_rot.py first"
