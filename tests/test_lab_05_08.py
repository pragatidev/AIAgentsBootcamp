"""Lab 05.08, reset_outcome typed by the student, both paths. A scripted model stands in for the real one here, and only here."""

import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from techcorp.tools import accounts
from techcorp.tools.accounts import dummy_runtime
from tests.fixtures.fake_model import FakeToolModel

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_08_typed_miss_both_paths.py"

GHOST = [
    AIMessage(content="", tool_calls=[{"name": "reset_password", "args": {"user_id": "E-9999"}, "id": "c1", "type": "tool_call"}]),
    "echo_tool",
]


@pytest.fixture(scope="module")
def lab():
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "get_chat_model", lambda **kw: FakeToolModel(script=list(GHOST)))
    try:
        yield runpy.run_path(str(LAB), run_name="__main__")
    finally:
        mp.undo()


@pytest.fixture(autouse=True)
def audit(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts, "AUDIT_PATH", path)
    return path


@pytest.mark.parametrize("which", ["package", "lab"])
def test_typed_miss_both_paths(lab, which):
    reset_outcome = accounts.reset_outcome if which == "package" else lab["reset_outcome"]
    assert reset_outcome("E-0000") == {"found": False, "reason": "unknown user E-0000"}
    assert reset_outcome("") == {"found": False, "reason": "no user id"}
    hit = reset_outcome("E-4101")
    assert hit["found"] is True and hit["user_id"] == "E-4101"
    assert len(hit["temporary_password"]) == 10 and hit["expires_in_hours"] == 24


def test_lab_tool_reads_the_envelope(lab, audit):
    tool = lab["lab_reset_password"]
    assert tool.func("E-4102", runtime=dummy_runtime("E-9999")) == {"found": False, "reason": "unknown user E-9999"}
    assert tool.func("E-4101", runtime=dummy_runtime(None)) == {"found": False, "reason": "no user id"}
    assert tool.func("E-4102", runtime=dummy_runtime("E-4101"))["user_id"] == "E-4101"
    assert not audit.exists()


def test_the_desk_reads_the_miss(monkeypatch, capsys, audit):
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: FakeToolModel(script=list(GHOST)))
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert 'tool reset_password {"found": false, "reason": "unknown user E-9999"}' in out
    assert out[-1].startswith("reply Done.")
    assert not audit.exists()
