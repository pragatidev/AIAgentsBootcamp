"""Lab 05.30, check typed by the student. A scripted model stands in for the real one here, and only here."""

import json
import re
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import config
from techcorp.agent import permissions
from techcorp.agent.context import DeskContext
from techcorp.tools import accounts
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_30_permissions_and_tenants.py"


class TicketScript:
    """Proposes the ticket's write on the human turn and echoes the tool result after it."""

    model = "ticket-script"

    def bind_tools(self, tools, **kwargs):
        return self

    def bind(self, **kwargs):
        return self

    def invoke(self, messages, **kwargs):
        last = messages[-1]
        if isinstance(last, HumanMessage):
            ticket = re.search(r"TC-\d+", last.content).group(0)
            name, args = ("grant_access", {"user_id": "E-4104", "share": "finance-q3"}) if ticket == "TC-1004" else ("reset_password", {"user_id": "E-4102"})
            return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "c1", "type": "tool_call"}])
        return AIMessage(content=f"Done: {last.content}")


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(accounts, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: TicketScript())

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    return run


def test_four_decisions_before_any_model(run_lab):
    _, out = run_lab()
    checks = {line.split()[1]: json.loads(line.split(" ", 2)[2]) for line in out if line.startswith("check ")}
    assert checks["employee_grant"]["reason"] == "role employee may not call grant_access"
    assert checks["eu_agent_grant"] is None
    assert checks["us_agent_grant"]["reason"] == "E-4104 is in region EU; this desk serves US"
    assert checks["empty_reset"]["reason"] == "no acting user in the request envelope"


def test_three_ways_and_the_empty_envelope_on_the_desk(run_lab):
    _, out = run_lab()
    assert "employee parked []" in out and "us_agent parked []" in out and "empty_envelope parked []" in out
    assert "eu_agent parked [('grant_access', {'user_id': 'E-4104', 'share': 'finance-q3'})]" in out
    assert any(line.startswith("us_agent tool grant_access error") and "this desk serves US" in line for line in out)
    assert any(line.startswith("empty_envelope tool reset_password error") and "no acting user" in line for line in out)


@pytest.mark.parametrize("tool, args, ctx", [
    ("grant_access", {"user_id": "E-4104", "share": "finance-q3"}, DeskContext(user_id="E-4104", role="employee", region="EU")),
    ("grant_access", {"user_id": "E-4104", "share": "finance-q3"}, DeskContext(user_id="E-4106", role="it_agent", region="EU")),
    ("grant_access", {"user_id": "E-4104", "share": "finance-q3"}, DeskContext(user_id="E-4101", role="it_agent", region="US")),
    ("grant_access", {"user_id": "E-4104", "share": "legal-share"}, DeskContext(user_id="E-4106", role="it_agent", region="EU")),
    ("grant_access", {"user_id": "E-4104", "share": "eng-tools"}, DeskContext(user_id="E-4106", role="it_agent", region="EU")),
    ("lookup_user", {"query": "E-4102"}, DeskContext(user_id="E-4101")),
    ("lookup_user", {"query": "Amina Cole"}, DeskContext(user_id="E-4101")),
    ("lookup_user", {"query": "E-0000"}, DeskContext(user_id="E-4101", role="it_agent")),
    ("reset_password", {"user_id": "E-4102"}, DeskContext()),
    ("delete_user", {}, DeskContext(user_id="E-4101")),
])
def test_typed_check_matches_package(run_lab, tool, args, ctx):
    lab, _ = run_lab()
    assert lab["check"](tool, args, ctx) == permissions.check(tool, args, ctx)


def test_the_break_lets_the_us_agent_through(run_lab, tmp_path):
    old = '''    if row.get("region") != region:
        return miss(f"{row['user_id']} is in region {row.get('region')}; this desk serves {region}")
'''
    _, out = run_lab(lab_copy(LAB, tmp_path, old, ""))
    assert "us_agent parked [('grant_access', {'user_id': 'E-4104', 'share': 'finance-q3'})]" in out
