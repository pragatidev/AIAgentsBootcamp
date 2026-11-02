"""Lab 03.20, where_in_window typed by the student, the budget and its break. A scripted model and summariser stand in for the real ones here, and only here."""

import runpy
from pathlib import Path

import pytest

from dataflow.context import agent, window_log
from dataflow.context.window_log import where_in_window as shipped_where
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_20_budget_and_window_log.py"


def scripted_chat_caller(num_predict: int = 80, num_ctx: int | None = None, tools=None):
    def call(messages: list) -> dict:
        return {"content": "Noted, happy to help with that question about your account today. " * 3, "tool_calls": [], "usage": {"input_tokens": 100, "output_tokens": 8, "total_tokens": 108}}

    call.tool_names = []
    call.model = "scripted"
    return call


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "chat_caller", scripted_chat_caller)
    monkeypatch.setattr(agent, "summarise_with_usage", lambda text, prompt=agent.SUMMARIZE_PROMPT: ("facts: DF-1001.", {"input_tokens": 60}))
    monkeypatch.setattr(agent, "applied_window", lambda: 8192)
    monkeypatch.setattr(agent, "CONTEXT_DIR", tmp_path)
    monkeypatch.setattr(window_log, "TRACES_DIR", tmp_path / "traces")
    return lambda path=LAB: runpy.run_path(str(path), run_name="__main__")


ROW = {"messages": [{"source": "system", "text": "Map"}, {"source": "notes", "text": "Never exceed 40 Dollars."}, {"source": "user", "text": "hi"}]}


@pytest.mark.parametrize("which", ["module", "lab"])
def test_where_in_window_both_copies(run, which):
    where = shipped_where if which == "module" else run()["where_in_window"]
    assert where(ROW, "40 dollars") == ["notes"]
    assert where(ROW, "refund") == []


def test_the_run_stays_under_and_the_rule_is_in_the_notes(capsys, run):
    run()
    out = capsys.readouterr().out.splitlines()
    assert "stayed_under True" in out and "stop final" in out
    assert any(line.startswith("rule_in_last_call ['notes'") for line in out)
    assert any(line.startswith("fold before") for line in out)
    assert [line.split()[-1] for line in out if line.startswith("stable_prefix")] == ["False", "True"]
    assert "map_problems []" in out and "map_version_in_log ['2']" in out


def test_the_break_stops_on_call_one(capsys, run, tmp_path):
    copy = lab_copy(LAB, tmp_path, "BUDGET = 900", "BUDGET = 200")
    run(copy)
    out = capsys.readouterr().out.splitlines()
    assert "stop budget" in out and "calls 0" in out
    assert any(line.startswith("stop budget tokens") for line in out)
