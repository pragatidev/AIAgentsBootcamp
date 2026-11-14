"""Lab 06.10.04 (18.4), parked_threads and blocked_by typed by the student. The fixture model routes T-3001 to refund
in place of the real one, here and only here; the refund ledger and the SQLite file are temp files the lab makes for
itself (it points DATAFLOW_REFUNDS_PATH at its own temp ledger; setting it here first makes monkeypatch put it back)."""

import runpy
import sqlite3

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_10_04_change_a_graph_under_parked_threads.py"
PARK_CHECK = "    parked = parked_threads(saver, live_graph)\n"
REPLY = "Refund issued for order DF-1001. Amount: 49.0."
KEYS_DONE = "keys ['actor', 'decision', 'order', 'refund', 'reply', 'route', 'ticket'] next () interrupts 0"


@pytest.fixture
def scripted(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_chat_model", lambda **kwargs: FakeChatModel(route="refund"))
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "unused.jsonl"))


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, [line for line in capsys.readouterr().out.splitlines() if not line.startswith("actor=")]


def test_lab_parks_two_then_each_change(scripted, capsys):
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    for thread_id in ("lab-18-4-a", "lab-18-4-b"):
        assert f"parked {thread_id} keys ['route', 'ticket'] next ('refund',) interrupts 1" in out
    assert "parked_threads {'lab-18-4-a': ('refund',), 'lab-18-4-b': ('refund',)}" in out
    one = out.index("change 1: added key priority")
    assert out[one + 1 : one + 6] == [
        "leaving [] blocked {} ship True",
        f"resume lab-18-4-a error none reply {REPLY}",
        "resume lab-18-4-a save_points 3 to 4 refunds_rows 0 to 1",
        "resume lab-18-4-a pending_writes []",
        f"after lab-18-4-a {KEYS_DONE}",
    ]
    two = out.index("change 2: refund renamed to refunds")
    assert out[two + 1 : two + 12] == [
        "leaving ['refund'] blocked {'lab-18-4-b': ('refund',)} ship False",
        "before lab-18-4-b keys ['route', 'ticket'] next () interrupts 0",
        "before lab-18-4-b reply None refunds_rows 1",
        "resume lab-18-4-b error none reply None",
        "resume lab-18-4-b save_points 3 to 3 refunds_rows 1 to 1",
        "resume lab-18-4-b pending_writes ['__resume__', '__interrupt__']",
        "after lab-18-4-b keys ['route', 'ticket'] next () interrupts 0",
        "after lab-18-4-b reply None refunds_rows 1",
        "parked_threads through renamed {}",
        "parked_threads through added_key {'lab-18-4-b': ('refund',)}",
        "rollback: refund is back",
    ]
    assert out[two + 12 : two + 20] == [
        "before lab-18-4-b keys ['route', 'ticket'] next ('refund',) interrupts 1",
        "before lab-18-4-b reply None refunds_rows 1",
        f"resume lab-18-4-b error none reply {REPLY}",
        "resume lab-18-4-b save_points 3 to 4 refunds_rows 1 to 2",
        "resume lab-18-4-b pending_writes []",
        f"after lab-18-4-b {KEYS_DONE}",
        f"after lab-18-4-b reply {REPLY} refunds_rows 2",
        "parked_threads {}",
    ]
    assert out[-1] == "refunds [('DF-1001', 49.0, 'reviewer approved'), ('DF-1001', 49.0, 'reviewer approved')]"


def test_typed_check_on_a_fresh_file(scripted, tmp_path, capsys):
    lab, _ = _run(LAB, capsys)
    saver = SqliteSaver(sqlite3.connect(str(tmp_path / "fresh.sqlite"), check_same_thread=False))
    live = build_v4_hitl(checkpointer=saver, model=FakeChatModel(route="refund"))
    live.invoke({"ticket": "I want a refund for order DF-1001."}, {"configurable": {"thread_id": "parked"}})
    lookup = build_v4_hitl(checkpointer=saver, model=FakeChatModel(route="lookup"))
    lookup.invoke({"ticket": "Where is order DF-1001?"}, {"configurable": {"thread_id": "done"}})
    assert lab["parked_threads"](saver, live) == {"parked": ("refund",)}
    renamed = lab["build_desk"](saver, state=lab["HitlStateV2"], refund_name="refunds")
    assert lab["parked_threads"](saver, renamed) == {}
    assert lab["blocked_by"](saver, live, renamed) == {"parked": ("refund",)}
    assert lab["blocked_by"](saver, live, lab["build_desk"](saver, state=lab["HitlStateV2"])) == {}
    assert capsys.readouterr().out.splitlines() == [
        "leaving ['refund'] blocked {'parked': ('refund',)} ship False",
        "leaving [] blocked {} ship True",
    ]
    saver.conn.close()


def test_break_check_through_the_new_graph_says_ship(scripted, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, PARK_CHECK, "    parked = parked_threads(saver, new_graph)\n")
    _, out = _run(broken, capsys)
    two = out.index("change 2: refund renamed to refunds")
    assert out[two + 1] == "leaving ['refund'] blocked {} ship True"
    assert "resume lab-18-4-b save_points 3 to 3 refunds_rows 1 to 1" in out
