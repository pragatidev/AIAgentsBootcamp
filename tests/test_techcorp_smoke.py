"""Smoke the TechCorp door: health, no key, a reset that parks, an approval by another person, a refusal. Scripted model, no live call."""

from __future__ import annotations

import json
import re

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from techcorp.serve import caller_for, create_app, parse_keys
from techcorp.tools import accounts

KEYS = parse_keys("emp-4101:E-4101:employee,agent-4106:E-4106:it_agent")


class TicketScript:
    """TC-1001 asks for its reset; TC-1002 refuses in the shape; after a tool result, it echoes it."""

    model = "ticket-script"

    def bind_tools(self, tools, **kwargs):
        return self

    def bind(self, **kwargs):
        return self

    def invoke(self, messages, **kwargs):
        last = messages[-1]
        if isinstance(last, HumanMessage):
            ticket = re.search(r"TC-\d+", last.content).group(0)
            if ticket == "TC-1001":
                return AIMessage(content="", tool_calls=[{"name": "reset_password", "args": {"user_id": "E-4101"}, "id": "r", "type": "tool_call"}])
            return AIMessage(content=f"I cannot help with that from the IT desk: no tool for VPN faults. Please contact Network Support. {ticket}")
        return AIMessage(content=f"Done. {last.content} TC-1001")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr("techcorp.agent.middleware.RUN_AUDIT_PATH", tmp_path / "run_audit.jsonl")
    return TestClient(create_app(model=TicketScript(), keys=KEYS))


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_no_key_is_401(client):
    assert client.post("/ticket", json={"ticket_id": "TC-1001", "text": "reset it"}).status_code == 401


def test_reset_parks_then_another_person_approves(client, tmp_path):
    parked = client.post("/ticket", json={"ticket_id": "TC-1001", "text": "I forgot my password."}, headers={"x-api-key": "emp-4101"}).json()
    assert parked["parked"] is True and parked["action_requests"][0]["name"] == "reset_password"
    assert parked["action_requests"][0]["description"].startswith("reset_password will act on E-4101.")
    assert not (tmp_path / "audit.jsonl").exists()
    refused = client.post("/resume", json={"thread_id": parked["thread_id"], "decision": "approve"}, headers={"x-api-key": "emp-4101"})
    assert refused.status_code == 403
    done = client.post("/resume", json={"thread_id": parked["thread_id"], "decision": "approve"}, headers={"x-api-key": "agent-4106"}).json()
    assert done["parked"] is False and "temporary_password" in done["reply"]
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and "temporary_password" not in lines[0]
    row = json.loads((tmp_path / "run_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert (row["user_id"], row["approver"], row["request_id"]) == ("E-4101", "E-4106", parked["request_id"])


def test_vpn_ticket_returns_the_refusal_shape(client):
    out = client.post("/ticket", json={"ticket_id": "TC-1002", "text": "VPN drops."}, headers={"x-api-key": "emp-4101"}).json()
    assert out["reply"].startswith("I cannot help with that from the IT desk:")


def test_the_body_cannot_name_another_caller(client):
    parked = client.post("/ticket", json={"ticket_id": "TC-1001", "text": "reset", "user_id": "E-4102"}, headers={"x-api-key": "emp-4101"}).json()
    assert "will act on E-4101." in parked["action_requests"][0]["description"]


def test_caller_comes_from_the_key_table_only():
    assert caller_for("emp-4101", KEYS) == {"user_id": "E-4101", "role": "employee", "region": "US"}
    assert caller_for("made-up", KEYS) is None and caller_for(None, KEYS) is None
