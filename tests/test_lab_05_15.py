"""Lab 05.15, the summarizer typed by the student and the limit. A scripted model stands in for the real one here, and only here."""

import runpy
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import config
from techcorp.agent import desk as desk_mod
from techcorp.agent.prompts import SUMMARY_PROMPT
from techcorp.tools import accounts
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_15_summarization_and_tool_limit.py"


class DeskScript(BaseChatModel):
    """Answers by what it is asked: the summary prompt gets four slots; a human turn gets a lookup; a tool result gets a sentence."""

    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "desk-script"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "DeskScript":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls += 1
        text = str(messages[-1].content)
        if "Summarize this TechCorp IT desk conversation" in text:
            reply = AIMessage(content="Employee id: E-4101\nTicket id: TC-1101\nDone: lookup_user found E-4101\nStill open: None")
        elif "look up E-4101, E-4102 and E-4103" in text:
            ids = ["E-4101", "E-4102", "E-4103"]
            reply = AIMessage(content="", tool_calls=[{"name": "lookup_user", "args": {"query": i}, "id": f"l{i}", "type": "tool_call"} for i in ids])
        elif isinstance(messages[-1], HumanMessage):
            reply = AIMessage(content="", tool_calls=[{"name": "lookup_user", "args": {"query": "E-4101"}, "id": f"c{self.calls}", "type": "tool_call"}])
        else:
            reply = AIMessage(content="Amina Cole is in Engineering. TC-1101")
        return ChatResult(generations=[ChatGeneration(message=reply)])


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts, "AUDIT_PATH", audit)

    def run(path: Path = LAB):
        model = DeskScript()
        monkeypatch.setattr(config, "get_chat_model", lambda **kw: model)
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines(), audit

    return run


def test_lab_summarizer_matches_desk_summarizer(run_lab):
    lab, _, _ = run_lab()
    typed, shipped = lab["desk_summarizer"](DeskScript()), desk_mod.desk_summarizer(DeskScript())
    assert lab["SUMMARY_PROMPT"] == SUMMARY_PROMPT == typed.summary_prompt == shipped.summary_prompt
    assert (typed.trigger, typed.keep) == (shipped.trigger, shipped.keep)


def test_summary_prompt_has_messages_slot(run_lab):
    lab, _, _ = run_lab()
    assert "{messages}" in lab["SUMMARY_PROMPT"]


def test_the_thread_stays_small_and_a_summary_is_written(run_lab):
    _, out, _ = run_lab()
    turns = [line.split() for line in out if line.startswith("turn ")]
    assert len(turns) == 6
    assert all(int(t[3]) <= 5 for t in turns), turns
    assert turns[-1][5] == "True" and int(turns[-1][7]) >= 1
    assert "summary_type human" in out
    assert "summary Here is a summary of the conversation to date:" in out and "Employee id: E-4101" in out


def test_summary_desk_cannot_write(run_lab):
    _, out, audit = run_lab()
    assert not audit.exists()


def test_limit_four_answers_three_lookups(run_lab):
    _, out, _ = run_lab()
    assert "run_limit 4 exit_behavior continue" in out
    assert "lookups_answered 3" in out


def test_limit_two_refuses_the_third_lookup(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, "LOOKUP_LIMIT = 4\n", "LOOKUP_LIMIT = 2\n")
    _, out, _ = run_lab(copy)
    assert "lookups_answered 2" in out
    assert any(line.startswith("tool error Tool call limit exceeded.") for line in out)
