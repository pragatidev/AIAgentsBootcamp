"""Lab 05.32, caller_for typed by the student; the door, the smoke steps and the eval set. A scripted model stands in for the real one here, and only here."""

import re
import runpy
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")
from langchain_core.messages import AIMessage, HumanMessage

import config
from techcorp import serve
from techcorp.tools import accounts
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_32_desk_behind_a_door.py"
RESETS = {"TC-1001", "TC-1005", "TC-1098"}


class TicketScript:
    """A reset ticket looks up, then asks for the reset; every other ticket refuses in the shape."""

    model = "ticket-script"

    def bind_tools(self, tools, **kwargs):
        return self

    def bind(self, **kwargs):
        return self

    def invoke(self, messages, **kwargs):
        ticket = re.search(r"TC-\d+", [m for m in messages if isinstance(m, HumanMessage)][-1].content).group(0)
        tools_seen = sum(1 for m in messages if getattr(m, "type", "") == "tool")
        if ticket in RESETS:
            name, args = ("lookup_user", {"query": "E-4101"}) if tools_seen == 0 else ("reset_password", {"user_id": "E-4101"})
            if tools_seen < 2:
                return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{tools_seen}", "type": "tool_call"}])
            return AIMessage(content=f"Your password is reset. {ticket}")
        return AIMessage(content=f"I cannot help with that from the IT desk: not this desk's job. Please contact Network Support. {ticket}")


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(accounts, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr("techcorp.agent.middleware.RUN_AUDIT_PATH", tmp_path / "run_audit.jsonl")
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: TicketScript())

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    return run


def test_five_smoke_steps_pass_on_the_door(run_lab):
    _, out = run_lab()
    assert [line.split()[2] for line in out if line.startswith("smoke ") and not line.startswith("smoke_")] == [
        "health", "no_key_refused", "reset_parked", "approved_once_no_secret", "vpn_refused_in_shape",
    ]
    assert "smoke_passed 5/5" in out


def test_every_eval_case_prints_a_row(run_lab):
    _, out = run_lab()
    rows = [line for line in out if line.startswith("eval ")]
    assert len(rows) == 15
    assert any(line.startswith("eval_passed ") for line in out)


@pytest.mark.parametrize("key", ["lab-employee-4101", "lab-agent-4106", "made-up", None, " lab-employee-4101 "])
def test_typed_caller_for_matches_package(run_lab, key):
    lab, _ = run_lab()
    assert lab["caller_for"](key, lab["KEYS"]) == serve.caller_for(key, lab["KEYS"])


def test_the_friendly_default_lets_a_keyless_request_in(run_lab, tmp_path):
    old = '    owner = keys.get((api_key or "").strip())\n    if owner is None:'
    new = '    owner = keys.get((api_key or "").strip()) or {"user_id": "E-4101", "role": "employee"}\n    if owner is None:'
    _, out = run_lab(lab_copy(LAB, tmp_path, old, new))
    assert any(line.startswith("smoke 2 no_key_refused pass False") for line in out)
    assert "smoke_passed 4/5" in out
