"""Lab 06.05.06 (14.5), the student's three policy tests typed in the lab. A fixture model stands in for the real one in
the ticket cell here, and only here; the refund ledger is a temp file through DATAFLOW_REFUNDS_PATH. The lab's last line
starts pytest on tests/test_dataflow_hitl.py, which the suite runs itself, so here that call is recorded, not made."""

import runpy
import subprocess

import pytest

import config
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_05_06_policy_lookup_free_refund_parks.py"
REPO_LEDGER = ROOT / "dataflow" / "data" / "refunds.jsonl"
RIGHT = 'model=FakeChatModel(route="refund"))\n'
WRONG = 'model=FakeChatModel(route="lookup"))\n'
NAMES = ["test_lookup_never_parks", "test_refund_always_parks", "test_refund_road_alone"]


@pytest.fixture
def desk(monkeypatch, tmp_path):
    """The ticket cell's model routes by the words in the ticket, the way the real one should."""

    class ByWords(FakeChatModel):
        def with_structured_output(self, schema, **kwargs):
            parent = self

            class _Runner:
                def invoke(self, messages, **kw):
                    text = str(messages[-1]["content"]).lower()
                    return {"route": "refund" if "refund" in text else "lookup"}

            return _Runner()

    monkeypatch.setattr(config, "get_chat_model", lambda **k: ByWords())
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "ledger" / "refunds.jsonl"))
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def _ledger_state():
    return REPO_LEDGER.read_bytes() if REPO_LEDGER.exists() else None


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_three_tests_pass_and_the_tickets_follow_the_policy(desk, capsys):
    before = _ledger_state()
    lab, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    assert out[3:6] == ["PASS " + name for name in NAMES]
    assert out[6] == "ticket T-3002 route lookup next ()"
    assert out[7].startswith("reply looked up DF-1002. Order DF-1002 is in_transit.")
    assert out[8:12] == [
        "ticket T-3001 route refund next ('refund',)",
        "reply None",
        "question Approve this refund of 49.0 on order DF-1001?",
        "refunds_rows 0",
    ]
    assert out[-1] == "pytest_exit 0"
    argv, kwargs = desk[-1]
    assert argv[1:] == ["-m", "pytest", "tests/test_dataflow_hitl.py", "-q"]
    for name in NAMES:
        lab[name]()
    assert _ledger_state() == before


def test_partial_run_never_asks_the_classifier(desk, capsys, monkeypatch):
    lab, _ = _run(LAB, capsys)
    asked = []
    monkeypatch.setattr(FakeChatModel, "with_structured_output", lambda self, *a, **k: asked.append(a) or None)
    lab["test_refund_road_alone"]()
    assert asked == []


def test_break_misrouted_refund_fails_the_policy_test(desk, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, RIGHT, WRONG)
    _, out = _run(broken, capsys)
    assert out[3] == "PASS test_lookup_never_parks"
    assert out[4].startswith("FAIL test_refund_always_parks looked up DF-1001. Order DF-1001 is delivered.")
    assert out[5] == "PASS test_refund_road_alone"
