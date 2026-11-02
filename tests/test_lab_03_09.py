"""Lab 03.09, total_input typed by the student, with the summariser counted. A scripted model and summariser stand in for the real ones here, and only here."""

import runpy
from pathlib import Path

import pytest

from dataflow.context import agent
from dataflow.context.agent import total_input

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_09_compare_compaction.py"


def scripted_chat_caller(num_predict: int = 80, num_ctx: int | None = None):
    def call(messages: list) -> dict:
        return {"content": "Noted, happy to help.", "tool_calls": [], "usage": {"input_tokens": 100}}

    call.tool_names = []
    return call


@pytest.fixture
def run(monkeypatch):
    monkeypatch.setattr(agent, "chat_caller", scripted_chat_caller)
    monkeypatch.setattr(agent, "summarise_with_usage", lambda text, prompt=agent.SUMMARIZE_PROMPT: ("facts: DF-1001.", {"input_tokens": 70}))
    monkeypatch.setattr(agent, "applied_window", lambda: None)
    return lambda: runpy.run_path(str(LAB), run_name="__main__")


TRACE = [
    {"turn": 1, "tokens": 40, "usage": {"input_tokens": 50}},
    {"event": "compact", "tokens_before": 200, "tokens_after": 80, "summariser_usage": {"input_tokens": 90}},
    {"turn": 2, "tokens": 90, "usage": {"input_tokens": None}},
    {"event": "compact", "tokens_before": 210, "tokens_after": 85, "summariser_usage": {}},
]


@pytest.mark.parametrize("which", ["module", "lab"])
def test_total_input_counts_the_summariser(run, which):
    total = total_input if which == "module" else run()["total_input"]
    assert total(TRACE) == {"desk": 50 + 90, "summariser": 90, "total": 230}
    assert total([]) == {"desk": 0, "summariser": 0, "total": 0}


def test_the_totals_add_up(capsys, run):
    run()
    out = dict(line.split(" ", 1) for line in capsys.readouterr().out.splitlines())
    folds = int(out["compactions"])
    assert folds > 0
    assert int(out["uncompacted_total_input"]) == 15 * 100
    assert int(out["compacted_desk_input"]) == 15 * 100
    assert int(out["summariser_input"]) == 70 * folds
    assert int(out["compacted_total_input"]) == 1500 + 70 * folds
