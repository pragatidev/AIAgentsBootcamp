"""Lab 05.14, write_gate typed by the student. A scripted model stands in for the real one here, and only here."""

import json
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from techcorp.agent.desk import DEFAULT_TOOLS, write_gate
from techcorp.tools import accounts
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_14_hitl_middleware_on_reset.py"


def _ask(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


RESET = _ask("reset_password", {"user_id": "E-4101"}, "r")
# approve thread, bare reject, reasoned reject, grant: each parks, then the model reads what came back.
SCRIPT = [RESET, "echo_tool", RESET, "echo_tool", RESET, "echo_tool", _ask("grant_access", {"user_id": "E-4104", "share": "finance-q3"}, "g"), "echo_tool"]


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts, "AUDIT_PATH", audit)

    def run(path: Path = LAB, script=SCRIPT):
        monkeypatch.setattr(config, "get_chat_model", lambda **kw: FakeToolModel(script=list(script)))
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines(), audit

    return run


def _gate_shape(gate) -> dict:
    return {name: rule["allowed_decisions"] for name, rule in gate.interrupt_on.items()}


def test_lab_gate_matches_desk_gate(run_lab):
    lab, _, _ = run_lab()
    assert _gate_shape(lab["write_gate"]()) == _gate_shape(write_gate())


def test_gate_names_are_real_tools(run_lab):
    lab, _, _ = run_lab()
    names = {t.name for t in DEFAULT_TOOLS}
    for gate in (lab["write_gate"](), write_gate()):
        assert set(gate.interrupt_on) <= names, set(gate.interrupt_on) - names
        assert set(gate.interrupt_on) == {"reset_password", "grant_access"}


def test_lab_parks_approves_once_and_audits_no_password(run_lab):
    _, out, audit = run_lab()
    assert "lab-4-14-approve parked True" in out
    assert "lab-4-14-approve description reset_password will act on E-4101. Requested by E-4101. The model asked with {\"user_id\": \"E-4101\"}." in out
    assert "audit_lines_after_park 0" in out and "audit_lines_after_approve 1" in out
    assert "audit_has_password False" in out
    row = json.loads(audit.read_text(encoding="utf-8").splitlines()[0])
    assert row["action"] == "reset_password" and "temporary_password" not in row
    assert "grant_parked True" in out


def test_reject_with_reason_writes_nothing_and_says_why(run_lab):
    _, out, _ = run_lab()
    assert "lab-4-14-reject tool_message_status error" in out
    assert any(line.startswith("lab-4-14-reject tool_message User rejected the tool call for `reset_password` with id r. The tool was not executed.") for line in out)
    assert "lab-4-14-reject-reason tool_message User rejected the tool call for `reset_password` with reason: Reviewer rejected the reset: identity not verified." in out
    assert "lab-4-14-reject audit_lines_added 0" in out and "lab-4-14-reject-reason audit_lines_added 0" in out


def test_misspelled_gate_lets_the_reset_through(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, 'for name in ("reset_password", "grant_access")', 'for name in ("reset_pasword", "grant_access")')
    lab, out, audit = run_lab(copy, [RESET, "echo_tool"] * 3 + [AIMessage(content="no grant today")])
    assert "lab-4-14-approve parked False" in out
    assert "reset_pasword" in lab["write_gate"]().interrupt_on
    assert len(audit.read_text(encoding="utf-8").splitlines()) == 3
