"""Lab 05.18, score_case typed by the student. A scripted model stands in for the real one here, and only here."""

import re
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import config
from techcorp.agent import evals
from techcorp.tools import accounts

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_18_iterate_the_prompt.py"
REFUSE = "I cannot help with that from the IT desk: not this desk's job. Please contact {}. {}"


class TicketScript:
    """Answers by the ticket in the last human message: TC-1001 looks up, then resets, then replies; the rest refuse."""

    model = "ticket-script"

    def bind_tools(self, tools, **kwargs):
        return self

    def bind(self, **kwargs):
        return self

    def invoke(self, messages, **kwargs):
        human = [m for m in messages if isinstance(m, HumanMessage)][-1].content
        ticket = re.search(r"TC-\d+", human).group(0)
        tools_seen = sum(1 for m in messages if getattr(m, "type", "") == "tool")
        if ticket != "TC-1001":
            team = "Procurement" if ticket == "TC-1099" else "Network Support"
            return AIMessage(content=REFUSE.format(team, ticket))
        steps = [("lookup_user", {"query": "E-4101"}), ("reset_password", {"user_id": "E-4101"})]
        if tools_seen < len(steps):
            name, args = steps[tools_seen]
            return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{tools_seen}", "type": "tool_call"}])
        return AIMessage(content="Your temporary password is ready. TC-1001")


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(accounts, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: TicketScript())
    lab = runpy.run_path(str(LAB), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_lab_prints_three_totals(run_lab):
    _, out = run_lab
    assert [line for line in out if line.startswith("total ")] == ["total weak 3/3", "total strong 3/3", "total iterated 3/3"]
    assert sum(1 for line in out if line.startswith("score ")) == 9


def test_score_case_lab_and_package_agree(run_lab):
    lab, _ = run_lab
    states = [
        {"messages": [AIMessage(content="", tool_calls=[{"name": "reset_password", "args": {}, "id": "a", "type": "tool_call"}]), AIMessage(content="Done. TC-1001")]},
        {"messages": [AIMessage(content=REFUSE.format("Procurement", "TC-1099"))]},
        {"messages": [AIMessage(content="Sorry, no. TC-1002")]},
    ]
    for case in evals.load_cases():
        for state in states:
            assert lab["score_case"](case, state) == evals.score_case(case, state)


def test_the_iterated_band_replaced_the_old_one(run_lab):
    lab, out = run_lab
    assert lab["TOOL_RULES_V1"] not in lab["ITERATED_PROMPT"]
    assert lab["TOOL_RULES_V2"] in lab["ITERATED_PROMPT"]
    assert out[0] == "changed_band " + lab["TOOL_RULES_V2"]
