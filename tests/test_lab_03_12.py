"""Lab 03.12, notes_block typed by the student. A scripted model stands in for the real one here, and only here."""

import json
import runpy
from pathlib import Path

import pytest

from dataflow.context import agent
from dataflow.context.agent import notes_block as shipped_notes_block

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_12_recover_from_notes.py"


def scripted_chat_caller(num_predict: int = 80, num_ctx: int | None = None, tools=None):
    def call(messages: list) -> dict:
        if "Approve the full amount" in str(messages[-1]["content"]):
            capped = any("40 dollars" in str(m.get("content")) for m in messages)
            text = "Approved for $40, the cap on this account." if capped else "Approved, 49 dollars."
        else:
            text = "Noted, happy to help with that question."
        return {"content": text, "tool_calls": [], "usage": {"input_tokens": 10}}

    call.tool_names = []
    return call


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "NOTES_PATH", tmp_path / "notes.json")
    monkeypatch.setattr(agent, "chat_caller", scripted_chat_caller)
    monkeypatch.setattr(agent, "applied_window", lambda: None)
    return lambda: runpy.run_path(str(LAB), run_name="__main__")


@pytest.mark.parametrize("which", ["module", "lab"])
def test_notes_block_both_copies(run, tmp_path, which):
    block = shipped_notes_block if which == "module" else run()["notes_block"]
    path = tmp_path / "copy.json"
    assert block(path) == ""
    path.write_text(json.dumps({"constraint": "cap 40"}), encoding="utf-8")
    assert block(path) == '\n\nNOTES\n{"constraint": "cap 40"}'


def test_notes_off_breaks_and_notes_on_holds(capsys, run):
    run()
    out = capsys.readouterr().out.splitlines()
    assert [line for line in out if line.startswith("summary_dropped_constraint")] == ["summary_dropped_constraint True"] * 2
    assert [line for line in out if line.startswith("cap_in_last_call")] == ["cap_in_last_call False", "cap_in_last_call True"]
    assert [line for line in out if line.startswith("verdict")] == ["verdict broke", "verdict held"]
