"""Lab 06.08.02 (17.2), carrier_error_handler and add_carrier typed by the student on the flaky carrier; the break
retries everything. The fixture model writes the reply; the receipts go to a temp file through DATAFLOW_RECEIPTS_PATH;
the lab copy's cache ttl is 1 second so the cache cell does not sleep 22."""

import runpy
from pathlib import Path

import pytest
from langgraph.errors import NodeError

import config
import dataflow.graphs.durable as durable
from dataflow.envelope import DeskContext
from dataflow.graphs.durable import build_durable_checked, carrier_miss_handler
from dataflow.tools.flaky import CarrierRejected, CarrierTimeout, reset_flaky, set_always_fail
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_08_02_retry_and_error_handler.py"
TTL = ("CACHE_TTL = 20  #", "CACHE_TTL = 1  #")
RETRY = ("            retry_on=CarrierTimeout,\n", "            retry_on=Exception,\n")
REPLY = "The carrier says in transit. The return window is 30 days."
TYPO = "Where is order DF-10O2? Tracking still says in transit."


@pytest.fixture
def fixture_model(monkeypatch, tmp_path):
    model = FakeChatModel(reply=REPLY)
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    receipts = tmp_path / "receipts.jsonl"
    monkeypatch.setenv("DATAFLOW_RECEIPTS_PATH", str(receipts))
    yield model
    reset_flaky()
    durable.reset_durable()
    assert receipts.exists()


def _copy(tmp_path: Path, *edits: tuple[str, str]) -> Path:
    copy = lab_copy_dataflow(LAB, tmp_path, *TTL)
    for old, new in edits:
        copy = lab_copy_dataflow(copy, tmp_path, old, new)
    return copy


def _lines(out: list[str], label: str) -> list[str]:
    return [line.strip() for line in out if line.startswith(f"   {label} ")]


def test_lab_retries_the_world_and_misses_bad_input_once(fixture_model, tmp_path, capsys):
    runpy.run_path(str(_copy(tmp_path)), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "model FakeChatModel None"
    assert out[1] == "langchain-core 1.6.2" and out[2] == "langgraph 1.2.11"
    assert _lines(out, "where_is_it") == [
        "where_is_it attempt 1 timeout",
        "where_is_it attempt 2 timeout",
        "where_is_it attempt 3 success",
    ]
    assert any(line.startswith("where_is_it carrier {'found': True, 'order_id': 'DF-1002', 'status': 'in_transit'") for line in out)
    assert _lines(out, "carrier_down") == [f"carrier_down attempt {n} timeout" for n in (1, 2, 3)]
    assert any(
        line.startswith("carrier_down carrier {'found': False, 'reason': 'carrier unreachable after retries', 'error': 'CarrierTimeout'}")
        for line in out
    )
    assert _lines(out, "typo") == ["typo attempt 1 rejected DF-10"]
    assert any(
        line.startswith("typo carrier {'found': False, 'reason': 'carrier rejected the order id', 'error': 'CarrierRejected'}")
        for line in out
    )
    assert out.count(f"reply {REPLY}") == 3
    assert "default_retry_on ValueError False ConnectionError True" in out
    assert out[-3:] == [
        "cache first policy_body_runs 1",
        "cache second policy_body_runs 1",
        "cache after_ttl policy_body_runs 2",
    ]


def test_typed_handler_and_node_match_the_package(fixture_model, tmp_path):
    lab = runpy.run_path(str(_copy(tmp_path)), run_name="__main__")
    for cause in (CarrierTimeout("carrier timeout"), CarrierRejected("carrier rejects order id 'DF-10'")):
        durable.reset_durable()
        error = NodeError(node="carrier_check", error=cause)
        mine, package = lab["carrier_error_handler"]({}, error), carrier_miss_handler({}, error)
        assert (mine.goto, mine.update) == (package.goto, package.update)
    for ticket in ("Where is order DF-1002? Tracking still says in transit.", TYPO):
        results = []
        for build in (lambda: lab["build_desk"](), lambda: build_durable_checked(model=fixture_model)):
            reset_flaky()
            durable.reset_durable()
            thread = {"configurable": {"thread_id": "test-17-2"}}
            out = build().invoke({"ticket": ticket}, thread, context=DeskContext(model=fixture_model))
            results.append((out["carrier"], out["log"], out["reply"]))
        assert results[0] == results[1]


def test_break_retry_everything_spends_three_attempts_on_bad_input(fixture_model, tmp_path, capsys):
    runpy.run_path(str(_copy(tmp_path, RETRY)), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert _lines(out, "typo") == [f"typo attempt {n} rejected DF-10" for n in (1, 2, 3)]
    typo = next(line for line in out if line.startswith("typo carrier "))
    assert "'reason': 'carrier rejected the order id'" in typo
    assert float(typo.rsplit(" ", 1)[1]) >= 0.6
    assert _lines(out, "where_is_it")[-1] == "where_is_it attempt 3 success"
