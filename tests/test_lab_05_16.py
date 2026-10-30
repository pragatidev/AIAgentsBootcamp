"""Lab 05.16, is_transient and resilience typed by the student. Scripted models stand in for the real ones here, and only here."""

import runpy
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import config
from techcorp.agent import resilience as module
from techcorp.agent.desk import build_techcorp_desk
from techcorp.tools import accounts
from techcorp.tools.accounts import lookup_user
from tests.fixtures.fake_model import FailingChatModel, ScriptedToolChatModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_16_model_fallback_and_retries.py"


class StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"model not found (status code: {status_code})")
        self.status_code = status_code


class GoodScript(BaseChatModel):
    """The trusted model: a lookup for a 'look me up' ticket, then a sentence; a sentence otherwise."""

    model: str = "good-script"

    @property
    def _llm_type(self) -> str:
        return "good-script"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "GoodScript":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        last = messages[-1]
        meta = {"model_name": "good-script"}
        if isinstance(last, HumanMessage) and "look me up" in str(last.content):
            uid = "E-9999" if "E-9999" in str(last.content) else "E-4106"
            reply = AIMessage(content="", tool_calls=[{"name": "lookup_user", "args": {"query": uid}, "id": "l1", "type": "tool_call"}], response_metadata=meta)
        else:
            reply = AIMessage(content="I cannot help with that from the IT desk: VPN faults. Please contact Network Support. TC-1002", response_metadata=meta)
        return ChatResult(generations=[ChatGeneration(message=reply)])


def fake_local(**kwargs):
    if kwargs.get("model") == "qwen3-does-not-exist-lab":
        return FailingChatModel(error=lambda: StatusError(404), fail_times=-1, script=[AIMessage(content="never")])
    if kwargs.get("base_url") == "http://127.0.0.1:1":
        return FailingChatModel(error=lambda: ConnectionError("connection refused"), fail_times=-1, script=[AIMessage(content="never")])
    raise AssertionError(kwargs)


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(accounts, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: GoodScript())
    monkeypatch.setattr(config, "get_local_chat_model", fake_local)

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    return run


def test_lab_prints_the_404_the_list_and_the_fallback(run_lab):
    _, out = run_lab()
    assert "bad_model_error StatusError status_code 404 transient False" in out
    assert "fallback_models ['good-script']" in out
    answered = [line for line in out if line.startswith("answered_by ")]
    assert answered[:2] == ["answered_by good-script", "answered_by good-script"]


def test_lab_counts_one_retry(run_lab):
    _, out = run_lab()
    assert "model_calls 3 faults_raised 1" in out
    assert "retries 1" in out


def test_tool_retry_recovers_one_fault_and_a_miss_is_not_retried(run_lab):
    _, out = run_lab()
    assert "lookup E-4106 tool_calls 2 tool_faults 1" in out
    assert "lookup E-9999 tool_calls 1 tool_faults 0" in out
    assert 'tool success {"found": false, "reason": "unknown user E-9999"}' in out


def test_retry_without_on_failure_hides_the_fallback(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, 'retry_on=is_transient, on_failure="error", ', "retry_on=is_transient, ")
    _, out = run_lab(copy)
    replies = [line for line in out if line.startswith("reply ")]
    assert replies[1].startswith("reply Model call failed after 3 attempts with ConnectionError")


@pytest.mark.parametrize("fault, primary_calls, fallback_calls, answer", [
    (dict(error=ConnectionError("blip"), fail_times=1), 2, 0, "primary"),
    (dict(error=lambda: StatusError(404), fail_times=-1), 1, 1, "fallback"),
    (dict(error=lambda: ConnectionError("down"), fail_times=-1), 3, 1, "fallback"),
])
def test_lab_resilience_matches_module(run_lab, fault, primary_calls, fallback_calls, answer):
    lab, _ = run_lab()
    for make in (lab["resilience"], module.resilience):
        primary = FailingChatModel(script=[AIMessage(content="primary")], **fault)
        fallback = ScriptedToolChatModel(script=[AIMessage(content="fallback")])
        desk = build_techcorp_desk(model=primary, tools=[lookup_user], middleware=make(fallback))
        out = desk.invoke({"messages": [HumanMessage(content="Ticket TC-1002: VPN?")]})
        assert out["messages"][-1].content == answer
        assert (primary.calls, fallback.calls) == (primary_calls, fallback_calls)
    for exc in (StatusError(404), StatusError(401), ConnectionError("x"), StatusError(503)):
        assert lab["is_transient"](exc) == module.is_transient(exc)
