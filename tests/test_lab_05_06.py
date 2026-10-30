"""Lab 05.06, answer_calls typed by the student. A scripted model stands in for the real one here, and only here."""

import json
import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from techcorp.agent import by_hand
from techcorp.tools import accounts
from techcorp.tools.accounts import dummy_runtime
from tests.fixtures.fake_model import FakeToolModel

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_06_bind_tools_and_read_the_call.py"


def _call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


TWO_HOPS = [
    AIMessage(content="", tool_calls=[_call("lookup_user", {"query": "E-4101"}, "c1")]),
    AIMessage(content="", tool_calls=[_call("reset_password", {"user_id": "E-4101"}, "c2")]),
    "echo_tool",
]


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts, "AUDIT_PATH", audit)

    def run(script, path: Path = LAB):
        monkeypatch.setattr(config, "get_chat_model", lambda **kw: FakeToolModel(script=list(script)))
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines(), audit

    return run


def test_lab_runs_two_hops_and_stops_final(run_lab):
    _, out, audit = run_lab(TWO_HOPS)
    assert out[0].startswith("model FakeToolModel")
    assert "max_hops 3" in out
    assert 'hop 1 proposed lookup_user {"query": "E-4101"} id c1' in out
    assert 'hop 2 proposed reset_password {"user_id": "E-4101"} id c2' in out
    assert "about_to_run reset_password for E-4101" in out
    assert out[-2:] == ["pairing []", "stop final"]
    assert len(audit.read_text(encoding="utf-8").splitlines()) == 1


def test_answer_calls_typed_matches_shipped(run_lab):
    lab, _, _ = run_lab(TWO_HOPS)
    ai = AIMessage(content="", tool_calls=[_call("lookup_user", {"query": "E-4101"}, "c1"), _call("lookup_user", {"query": "Ben Ortiz"}, "c2")])
    typed = lab["answer_calls"](ai, dummy_runtime("E-4101"))
    shipped = by_hand.answer_calls(ai, dummy_runtime("E-4101"))
    assert [m.tool_call_id for m in typed] == [m.tool_call_id for m in shipped] == ["c1", "c2"]
    assert [m.content for m in typed] == [m.content for m in shipped]
    unknown = AIMessage(content="", tool_calls=[_call("delete_user", {"user_id": "E-4101"}, "c9")])
    assert json.loads(lab["answer_calls"](unknown, dummy_runtime("E-4101"))[0].content) == {"found": False, "reason": "unknown tool delete_user"}


def test_envelope_wins_over_the_model_id(run_lab):
    lab, _, _ = run_lab(TWO_HOPS)
    ai = AIMessage(content="", tool_calls=[_call("reset_password", {"user_id": "E-4102"}, "c3")])
    assert json.loads(lab["answer_calls"](ai, dummy_runtime("E-4101"))[0].content)["user_id"] == "E-4101"


def test_a_model_that_always_asks_stops_at_max_hops(run_lab):
    always = [AIMessage(content="", tool_calls=[_call("lookup_user", {"query": "E-4101"}, "c1")])]
    _, out, _ = run_lab(always)
    assert out[-1] == "stop max_hops"
    assert sum(1 for line in out if " proposed lookup_user " in line) == 3


def test_the_break_is_caught_by_the_pairing_check(run_lab, tmp_path):
    text = LAB.read_text(encoding="utf-8")
    code = 'json.dumps(result), tool_call_id=call["id"], name=name'
    assert text.count(code) == 1
    copy = tmp_path / "labs" / LAB.name
    copy.parent.mkdir()
    data = tmp_path / "techcorp" / "data"
    data.mkdir(parents=True)
    (data / "tickets.jsonl").write_bytes((LAB.parents[1] / "techcorp" / "data" / "tickets.jsonl").read_bytes())
    copy.write_text(text.replace(code, 'json.dumps(result), tool_call_id="not-the-real-id", name=name'), encoding="utf-8")
    _, out, _ = run_lab(TWO_HOPS, copy)
    pairing = [line for line in out if line.startswith("pairing ")][0]
    assert "unanswered call c1" in pairing and "unanswered call c2" in pairing
    assert "stray result not-the-real-id" in pairing
