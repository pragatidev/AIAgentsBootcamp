"""Lab 05.20, acting_user typed by the student. A scripted model stands in for the real one here, and only here."""

import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

import config
from techcorp.agent.context import DeskContext
from techcorp.tools import accounts
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_20_runtime_context_user_id.py"


def _reset(user_id: str, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": "reset_password", "args": {"user_id": user_id}, "id": call_id, "type": "tool_call"}])


SCRIPT = [_reset("E-4101", "r1"), "echo_tool", _reset("E-4102", "r2"), "echo_tool", _reset("E-4102", "r3"), "echo_tool"]


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts, "AUDIT_PATH", audit)
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: FakeToolModel(script=list(SCRIPT)))

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines(), audit

    return run


def test_four_envelopes(run_lab):
    _, out, _ = run_lab()
    assert out[:4] == [
        'acting same {"ok": true, "user_id": "E-4101", "requested": "E-4101", "mismatch": false}',
        'acting different {"ok": true, "user_id": "E-4101", "requested": "E-4102", "mismatch": true}',
        'acting empty {"ok": false, "reason": "no acting user in the request envelope"}',
        'acting blank {"ok": false, "reason": "no acting user in the request envelope"}',
    ]


@pytest.mark.parametrize("ctx, requested", [
    (DeskContext(user_id="E-4101"), "E-4101"),
    (DeskContext(user_id="E-4101"), "E-4102"),
    (DeskContext(), "E-4102"),
    (DeskContext(user_id="  "), "E-4102"),
    (DeskContext(user_id="E-4101"), None),
])
def test_acting_user_lab_and_package_agree(run_lab, ctx, requested):
    lab, _, _ = run_lab()
    runtime = SimpleNamespace(context=ctx)
    assert lab["acting_user"](runtime, requested) == accounts.acting_user(runtime, requested)


def test_mismatch_run_acts_on_the_envelope_and_marks_the_audit(run_lab):
    _, out, audit = run_lab()
    assert "mismatch gate_says reset_password will act on E-4101. Requested by E-4101. The model asked with {\"user_id\": \"E-4102\"}." in out
    result = [line for line in out if line.startswith("mismatch tool_result reset_password ")][0]
    payload = json.loads(result.split(" ", 3)[3])
    assert payload["user_id"] == "E-4101" and payload["requested_user_id_ignored"] == "E-4102"
    assert "mismatch audit user_id E-4101 requested_user_id E-4102 mismatch True" in out


def test_empty_envelope_is_a_typed_miss(run_lab):
    _, out, _ = run_lab()
    assert 'empty tool_result reset_password {"found": false, "reason": "no acting user in the request envelope"}' in out
    assert not any(line.startswith("empty audit ") for line in out)


def test_the_break_lets_the_typed_id_through(run_lab, tmp_path):
    body = '''    if envelope is None:
        return {"ok": False, "reason": "no acting user in the request envelope"}
    return {"ok": True, "user_id": envelope, "requested": asked, "mismatch": asked is not None and asked.lower() != envelope.lower()}
'''
    copy = lab_copy(LAB, tmp_path, body, '    return {"ok": True, "user_id": envelope or asked, "requested": asked, "mismatch": False}\n')
    _, out, _ = run_lab(copy)
    assert out[2] == 'acting empty {"ok": true, "user_id": "E-4102", "requested": "E-4102", "mismatch": false}'
