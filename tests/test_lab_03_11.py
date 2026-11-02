"""Lab 03.11, write_note typed by the student, with the protected key. A scripted model stands in for the real one here, and only here."""

import json
import runpy
from pathlib import Path

import pytest

from dataflow.context import agent
from dataflow.context.agent import write_note as shipped_write_note

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_11_notes_file.py"

# Ticket text -> the notes the scripted model asks to write. Ticket three tries the rule again.
WRITES = {
    "I am customer": [("customer", "C-2001"), ("order", "DF-1001")],
    "HARD CONSTRAINT": [("constraint", "Refunds never exceed 40 dollars.")],
    "Please note": [("constraint", "Customer prefers email."), ("preference", "Email only.")],
}


def scripted_context_caller(**_kw):
    def call(messages: list) -> dict:
        if messages[-1]["role"] == "tool":
            return {"content": "Noted.", "tool_calls": [], "usage": {}}
        ticket = messages[-1]["content"]
        writes = next(v for k, v in WRITES.items() if ticket.startswith(k))
        calls = [
            {"id": f"w{i}", "name": "write_note", "arguments": {"key": key, "value": value}}
            for i, (key, value) in enumerate(writes)
        ]
        return {"content": "", "tool_calls": calls, "usage": {}}

    call.tool_names = ["write_note"]
    return call


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "NOTES_PATH", tmp_path / "notes.json")
    monkeypatch.setattr(agent, "context_caller", scripted_context_caller)
    monkeypatch.setattr(agent, "applied_window", lambda: None)
    return lambda: runpy.run_path(str(LAB), run_name="__main__")


@pytest.mark.parametrize("which", ["module", "lab"])
def test_write_note_both_copies(run, tmp_path, which):
    write_note = shipped_write_note if which == "module" else run()["write_note"]
    path = tmp_path / "copy.json"
    assert json.loads(write_note("constraint", "cap 40", path))["ok"] is True
    assert json.loads(write_note("order", "DF-1001", path))["notes"] == {"constraint": "cap 40", "order": "DF-1001"}
    refused = json.loads(write_note("constraint", "Customer prefers email.", path))
    assert refused == {"ok": False, "key": "constraint", "reason": "protected key, ask a person"}
    assert json.loads(path.read_text(encoding="utf-8"))["constraint"] == "cap 40"


def test_the_cap_survives_the_planted_write_and_the_model(capsys, run, tmp_path):
    run()
    out = capsys.readouterr().out.splitlines()
    notes = json.loads((tmp_path / "notes.json").read_text(encoding="utf-8"))
    assert notes == {
        "customer": "C-2001",
        "order": "DF-1001",
        "constraint": "Refunds never exceed 40 dollars.",
        "preference": "Email only.",
    }
    assert any(line.startswith("planted_write") and "protected key, ask a person" in line for line in out)
    assert "write constraint = Customer prefers email. -> False" in out
    assert "check_this_note preference = Email only." in out
