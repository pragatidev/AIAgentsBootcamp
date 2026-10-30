"""Lab 05.24, answer_ticket typed by the student, and the package's rule: nothing builds a model at import."""

import importlib
import runpy
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from techcorp.agent import desk as desk_mod
from techcorp.tools import accounts
from tests.fixtures.fake_model import FakeToolModel

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_24_package_with_tests.py"


def _reset_script() -> list:
    call = {"name": "reset_password", "args": {"user_id": "E-4101"}, "id": "call_reset", "type": "tool_call"}
    return [AIMessage(content="", tool_calls=[call]), "echo_tool"]


def test_importing_the_package_builds_no_model(monkeypatch):
    def refuse(**kwargs):
        raise AssertionError("model built at import")

    monkeypatch.setattr(config, "get_chat_model", refuse)
    for name in list(sys.modules):
        if name == "techcorp" or name.startswith("techcorp."):
            monkeypatch.delitem(sys.modules, name)
    importlib.import_module("techcorp.agent")
    importlib.import_module("techcorp.tools")
    runpy.run_path(str(LAB), run_name="lab_05_24")


def test_answer_ticket_lab_and_package_agree(monkeypatch, tmp_path):
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts, "AUDIT_PATH", audit)
    lab = runpy.run_path(str(LAB), run_name="lab_05_24")
    parked = [f(t, "E-4101", model=FakeToolModel(script=_reset_script())) for f, t in ((lab["answer_ticket"], "Ticket TC-1001: reset it."), (desk_mod.answer_ticket, "Ticket TC-1001: reset it."))]
    assert parked[0] == parked[1]
    assert parked[0].startswith("Waiting for a person to approve: reset_password will act on E-4101.")
    refusal = "I cannot help with that from the IT desk: VPN faults. Please contact Network Support. TC-1002"
    replies = [f("Ticket TC-1002: VPN drops.", "E-4102", model=FakeToolModel(script=[AIMessage(content=refusal)])) for f in (lab["answer_ticket"], desk_mod.answer_ticket)]
    assert replies == [refusal, refusal]
    assert not audit.exists()
