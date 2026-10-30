"""Lab 05.26, handle_ticket typed by the student. A scripted model stands in for the real one here, and only here."""

import json
import re
import runpy
import subprocess
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from techcorp.agent import desk as desk_mod
from techcorp.agent.desk import build_techcorp_desk
from techcorp.tools import accounts
from tests.fixtures.fake_model import FakeToolModel

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_26_portfolio_techcorp_desk.py"
APPROVE = {"decisions": [{"type": "approve"}]}
REFUSE = "I cannot help with that from the IT desk: {}. Please contact {}. {}"


def _reset_script() -> list:
    call = {"name": "reset_password", "args": {"user_id": "E-4101"}, "id": "call_reset", "type": "tool_call"}
    return [AIMessage(content="", tool_calls=[call]), "echo_tool"]


@pytest.fixture
def audit(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts, "AUDIT_PATH", path)
    return path


@pytest.fixture
def lab():
    return runpy.run_path(str(LAB), run_name="lab_05_26")


@pytest.mark.parametrize("which", ["lab", "package"])
def test_handle_ticket_lab_and_package_agree(lab, audit, which):
    handle = lab["handle_ticket"] if which == "lab" else desk_mod.handle_ticket
    parked = handle(build_techcorp_desk(model=FakeToolModel(script=_reset_script())), "Ticket TC-1001: reset it.", user_id="E-4101", thread_id="p")
    assert parked["parked"] is True and parked["action_requests"][0]["name"] == "reset_password"
    assert not audit.exists()
    done = handle(build_techcorp_desk(model=FakeToolModel(script=_reset_script())), "Ticket TC-1001: reset it.", user_id="E-4101", thread_id="a", decision=APPROVE)
    assert re.search(r"\b[0-9a-f]{10}\b", done["reply"])
    lines = audit.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    # The resumed run carries the envelope's request id, so the audit line can be traced to its request.
    assert len(json.loads(lines[0])["request_id"]) == 32


def test_reject_decision_writes_no_audit(lab, audit):
    out = lab["handle_ticket"](
        build_techcorp_desk(model=FakeToolModel(script=_reset_script())), "Ticket TC-1001: reset it.",
        user_id="E-4101", thread_id="r", decision={"decisions": [{"type": "reject", "message": "not today"}]},
    )
    assert out["parked"] is True and "not today" in out["reply"]
    assert not audit.exists()


def test_main_prints_the_checks(lab, audit, monkeypatch, capsys):
    script = _reset_script() + [
        AIMessage(content=REFUSE.format("VPN faults are not this desk's", "Network Support", "TC-1002")),
        AIMessage(content=REFUSE.format("we do not buy hardware", "Procurement", "TC-1099")),
    ]
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: FakeToolModel(script=script))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="12 passed in 1.00s\n", stderr=""))
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "gated reset_password ['approve', 'edit', 'reject', 'respond']" in out
    assert "reset_parked True" in out and "reset_reply_has_token True" in out
    assert "vpn_refused_in_shape True" in out and "oos_refused_in_shape True" in out
    assert "audit_lines_added 1" in out
    row = json.loads([line for line in out if line.startswith("audit_line ")][0].removeprefix("audit_line "))
    assert row["action"] == "reset_password" and "temporary_password" not in row
    assert out[-2:] == ["pytest 12 passed in 1.00s", "exit_code 0"]
