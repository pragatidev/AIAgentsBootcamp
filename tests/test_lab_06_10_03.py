"""Lab 06.10.03 (18.3), traced_run and first_failure typed by the student. The desk calls no model. Traces go to a temp
folder through the tracer's TRACES_DIR, so the repo's dataflow/data/traces is untouched."""

import runpy

import pytest

from dataflow.ops import tracer as tracer_mod
from dataflow.tools.flaky import reset_flaky
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_10_03_read_a_failed_run.py"
TICKET_LINE = 'ticket_text = ticket["text"]\n'
PLANTED = 'ticket_text = ticket["text"].replace("DF-1002", "DF-9999")\n'
CARRIER_ERROR = "CarrierTimeout: carrier timeout on attempt 1 for DF-1002"
T3002 = "Where is order DF-1002? Tracking still says in transit."


@pytest.fixture
def traces(monkeypatch, tmp_path):
    folder = tmp_path / "traces"
    monkeypatch.setattr(tracer_mod, "TRACES_DIR", folder)
    yield folder
    reset_flaky()


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_lab_finds_the_carrier(traces, capsys):
    _, out = _run(LAB, capsys)
    assert out[:3] == ["model none: this desk calls no model", "langchain-core 1.6.2", "langgraph 1.2.11"]
    start = out.index("run_failed CarrierTimeout carrier timeout on attempt 1 for DF-1002")
    assert out[start + 2 : start + 7] == [
        "failed_span tool fetch_carrier_status",
        "node carrier",
        "input {'ticket': '" + T3002 + "', 'order_id': 'DF-1002'}",
        "error " + CARRIER_ERROR,
        "checkpoint_next ('carrier',)",
    ]
    assert out[out.index("waterfall") + 1].startswith("run lab-18-3 ")
    assert sum("FAIL " + CARRIER_ERROR in line for line in out) == 4
    assert len(list(traces.glob("*.jsonl"))) == 1


def test_first_failure_on_a_fresh_desk(traces, capsys):
    lab, _ = _run(LAB, capsys)
    reset_flaky()
    graph = lab["build_small_desk"]()
    trace_file, config = lab["traced_run"](graph, "Where is order DF-1001?", "t")
    found = lab["first_failure"](trace_file, graph, config)
    assert found["node"] == "carrier" and found["input"]["order_id"] == "DF-1001"
    assert found["error"] == "CarrierTimeout: carrier timeout on attempt 1 for DF-1001"
    reset_flaky()
    graph = lab["build_small_desk"]()
    for _ in range(2):
        with pytest.raises(Exception):
            graph.invoke({"ticket": "DF-1001"}, {"configurable": {"thread_id": "warm"}})
    trace_file, config = lab["traced_run"](graph, "Where is order DF-1001?", "ok")
    assert lab["first_failure"](trace_file, graph, config) is None
    assert "no failure in this trace" in capsys.readouterr().out


def test_break_planted_bad_order_finds_check(traces, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, TICKET_LINE, PLANTED)
    _, out = _run(broken, capsys)
    start = out.index("run_failed ValueError unknown order DF-9999")
    assert out[start + 2 : start + 7] == [
        "failed_span chain check",
        "node check",
        "input {'ticket': 'Where is order DF-9999? Tracking still says in transit.', 'order_id': 'DF-9999'}",
        "error ValueError: unknown order DF-9999",
        "checkpoint_next ('check',)",
    ]
    waterfall = out[out.index("waterfall") + 1 :]
    assert not any("carrier" in line for line in waterfall)


def test_raw_trace_lines_in_file_order(traces, capsys):
    # LG-R7: the last cell prints the trace file's lines as they sit on disk, each after its line number.
    import json

    _, out = _run(LAB, capsys)
    start = next(i for i, line in enumerate(out) if line.startswith("trace_file_lines "))
    raw = out[start + 1 :]
    numbers, lines = zip(*(line.split(" ", 1) for line in raw))
    assert list(numbers) == [str(n) for n in range(1, len(raw) + 1)]
    assert list(lines) == next(traces.glob("*.jsonl")).read_text(encoding="utf-8").splitlines()
    spans = [json.loads(line) for line in lines]
    assert [(span["kind"], span["name"], span["status"]) for span in spans] == [
        ("chain", "stash", "ok"),
        ("chain", "check", "ok"),
        ("tool", "fetch_carrier_status", "error"),
        ("chain", "carrier", "error"),
        ("chain", "LangGraph", "error"),
        ("run", "lab-18-3", "error"),
    ]
    assert {span.get("error") for span in spans[2:]} == {CARRIER_ERROR}
