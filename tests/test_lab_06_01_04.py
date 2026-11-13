"""Lab 06.01.04 (10.4), the student's three node tests typed in the lab. A scripted classifier stands in for the real
model in the lab's first run here, and only here; the break is run with the model port dead."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs import v1_triage
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_01_04_invoke_and_test.py"
NAMES = ("test_classify_alone", "test_lookup_miss", "test_classify_node_on_a_fresh_graph")


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="orders"))
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://127.0.0.1:1")


def test_lab_runs_the_ticket_and_three_tests_pass(scripted, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[-7:-4] == [f"PASS {name}" for name in NAMES]
    assert out[-3:] == [
        "route orders",
        "order {'found': True, 'order_id': 'DF-1001', 'item': 'desk lamp', 'status': 'delivered', 'days_since_delivery': 12, "
        "'amount': 49.0, 'customer_id': 'C-2001', 'region': 'NA'}",
        "reply Order DF-1001 is delivered. Item: desk lamp.",
    ]


def test_the_students_tests_pass_when_called(scripted):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    for name in NAMES:
        lab[name]()


def test_break_without_the_injected_model_fails_on_the_connection(scripted, tmp_path, monkeypatch, capsys):
    # classify asks v1_triage's own get_chat_model when it has no model: the student's path, ChatOllama, port dead.
    monkeypatch.setattr(v1_triage, "get_chat_model", config.get_local_chat_model)
    broken = lab_copy_dataflow(LAB, tmp_path, ', model=FakeChatModel(route="policy"))', ")")
    lab = runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[-7].startswith("FAIL test_classify_alone httpx.ConnectError: ")
    assert out[-6:-4] == ["PASS test_lookup_miss", "PASS test_classify_node_on_a_fresh_graph"]
    with pytest.raises(Exception) as err:
        lab["test_classify_alone"]()
    assert type(err.value).__name__ == "ConnectError"
