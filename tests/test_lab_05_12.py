"""Lab 05.12, build_desk typed by the student. A scripted model stands in for the real one here, and only here."""

import json
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from techcorp.agent.desk import build_techcorp_desk, run_ticket
from techcorp.agent.prompts import DESK_SYSTEM_PROMPT
from techcorp.tools import accounts
from techcorp.tools.accounts import grant_access, lookup_user
from tests.fixtures.fake_model import FakeToolModel

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_12_build_the_desk.py"
REFUSAL = "I cannot help with that from the IT desk: {}. Please contact Network Support. {}"


def _reset_script() -> list:
    call = {"name": "reset_password", "args": {"user_id": "E-4101"}, "id": "call_reset", "type": "tool_call"}
    return [AIMessage(content="", tool_calls=[call]), "echo_tool"]


@pytest.fixture
def audit(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts, "AUDIT_PATH", path)
    return path


@pytest.fixture
def lab(monkeypatch, audit, capsys):
    script = _reset_script() + [
        AIMessage(content=REFUSAL.format("VPN faults are not this desk's", "TC-1002")),
        AIMessage(content=REFUSAL.format("installs need a person", "TC-1003")),
    ]
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: FakeToolModel(script=script))
    globals_ = runpy.run_path(str(LAB), run_name="__main__")
    globals_["_out"] = capsys.readouterr().out.splitlines()
    return globals_


def _payloads(state: dict) -> list[dict]:
    return [json.loads(m.content) for m in state["messages"] if m.type == "tool" and m.content.startswith("{")]


def test_lab_prints_nodes_and_three_transcripts(lab):
    out = lab["_out"]
    assert "nodes ['__start__', 'model', 'tools', '__end__']" in out
    assert [line.split()[1] for line in out if line.startswith("ticket ")] == ["TC-1001", "TC-1002", "TC-1003"]
    assert [line for line in out if line.startswith("refusal_shape")] == ["refusal_shape False", "refusal_shape True", "refusal_shape True"]


def test_lab_desk_matches_package_desk(lab, audit):
    lab_desk = lab["build_desk"](FakeToolModel(script=_reset_script()), lab["TOOLS"], DESK_SYSTEM_PROMPT)
    package_desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script()), middleware=[])
    for desk in (lab_desk, package_desk):
        assert set(desk.get_graph().nodes) == {"__start__", "model", "tools", "__end__"}
        state = run_ticket(desk, "Ticket TC-1001: reset my password.", user_id="E-4101")
        token = [p for p in _payloads(state) if p.get("found")][0]["temporary_password"]
        assert token in state["messages"][-1].content


def test_desk_without_reset_cannot_reset(lab, audit):
    before = audit.read_text(encoding="utf-8").splitlines() if audit.exists() else []
    desk = lab["build_desk"](FakeToolModel(script=_reset_script()), [lookup_user, grant_access], DESK_SYSTEM_PROMPT)
    state = run_ticket(desk, "Ticket TC-1001: reset my password.", user_id="E-4101")
    tool_messages = [m for m in state["messages"] if m.type == "tool"]
    assert tool_messages[0].content.startswith("Error: reset_password is not a valid tool")
    assert not any("temporary_password" in str(m.content) for m in tool_messages)
    after = audit.read_text(encoding="utf-8").splitlines() if audit.exists() else []
    assert after == before
