"""Lab 06.08.03 (17.3), write_receipt and send_receipt typed by the student; the break writes the receipt with the plain
function under the task. The database and the receipts are temp files through DATAFLOW_CHECKPOINTS_PATH and
DATAFLOW_RECEIPTS_PATH; the fixture model writes the reply."""

import runpy

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

import config
import dataflow.graphs.durable as durable
from dataflow.envelope import DeskContext
from dataflow.graphs.durable import count_receipts, read_receipts, set_crash_after_receipt
from dataflow.tools.flaky import reset_flaky
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_08_03_task_survives_crash.py"
TASK = "    row = write_receipt(ticket, order_id, status).result()\n"
DIRECT = "    row = write_receipt.func(ticket, order_id, status)\n"
REPLY = "Order DF-1002 is in transit. The return window is 30 days."
TICKET = "Where is order DF-1002? Tracking still says in transit."
REPO_FILES = [ROOT / "dataflow" / "data" / name for name in ("receipts.jsonl", "checkpoints_14.sqlite")]


@pytest.fixture
def temp_files(monkeypatch, tmp_path):
    model = FakeChatModel(reply=REPLY)
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    monkeypatch.setenv("DATAFLOW_CHECKPOINTS_PATH", str(tmp_path / "checkpoints.sqlite"))
    monkeypatch.setenv("DATAFLOW_RECEIPTS_PATH", str(tmp_path / "receipts.jsonl"))
    before = [(p.exists(), p.stat().st_mtime if p.exists() else None) for p in REPO_FILES]
    yield model
    set_crash_after_receipt(False)
    reset_flaky()
    durable.reset_durable()
    assert [(p.exists(), p.stat().st_mtime if p.exists() else None) for p in REPO_FILES] == before


def test_lab_crash_then_resume_keeps_one_receipt(temp_files, tmp_path, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "model FakeChatModel None"
    assert out[1] == "langchain-core 1.6.2" and out[2] == "langgraph 1.2.11"
    assert out[3] == f"db {(tmp_path / 'checkpoints.sqlite').as_posix()}"
    assert "planted_crash planted crash after the receipt task" in out
    assert "receipts_after_crash 1 next ('send_receipt',) carrier_calls 3" in out
    assert f"reply {REPLY}" in out
    assert "receipts_after_resume 1 carrier_calls 3" in out
    assert "task_remembered True" in out
    assert out[-2:] == [
        "durability exit save_points_after_crash 1 receipts_after_resume 1",
        "durability sync save_points_after_crash 3 receipts_after_resume 1",
    ]


def test_typed_task_and_node_match_the_package(temp_files, tmp_path):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    durable.reset_durable()
    results = []
    for name, build in (("mine", lab["build_desk"]), ("package", None)):
        (tmp_path / "receipts.jsonl").unlink(missing_ok=True)
        with SqliteSaver.from_conn_string(str(tmp_path / f"{name}-run.sqlite")) as saver:
            graph = build(saver) if build else durable.build_durable(checkpointer=saver, model=temp_files)
            thread = {"configurable": {"thread_id": f"test-17-3-{name}"}}
            reset_flaky()
            set_crash_after_receipt(True)
            with pytest.raises(RuntimeError, match="planted crash after the receipt task"):
                graph.invoke({"ticket": TICKET}, thread, context=DeskContext(model=temp_files))
            crashed = count_receipts()
            set_crash_after_receipt(False)
            out = graph.invoke(None, thread, context=DeskContext(model=temp_files))
            results.append((crashed, count_receipts(), read_receipts(), out["order"]))
    assert results[0] == results[1]
    assert results[0][:2] == (1, 1)


def test_break_plain_write_gives_two_receipts(temp_files, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, TASK, DIRECT)
    runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "receipts_after_crash 1 next ('send_receipt',) carrier_calls 3" in out
    assert "receipts_after_resume 2 carrier_calls 3" in out
    assert "task_remembered False" in out
