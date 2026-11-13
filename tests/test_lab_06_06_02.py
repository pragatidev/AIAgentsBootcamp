"""Lab 06.06.02 (15.2, first half), watch typed by the student. A fixture model stands in for the real one here, and
only here. The fixture's reply reaches the messages lane whole; the real model's arrives token by token (the capture)."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs.v5_stream import build_v5_stream
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_06_02_stream.py"
REPLY = "Your refund for DF-1001 is on its way."
MODES = 'stream_mode=["updates", "messages", "custom"]'
NODES = ["ingest", "read_pref", "classify", "orders_desk", "write_pref", "speak"]


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="orders", reply=REPLY))


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_lab_prints_every_lane(scripted, capsys):
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    assert [line.split()[1] for line in out if line.startswith("node ")] == NODES
    assert "node classify wrote ['route']" in out
    assert "node speak wrote ['messages', 'reply']" in out
    progress = [line for line in out if line.startswith("progress ")]
    assert progress == ["progress calling the model", "progress model finished"]
    assert f"tokens speak ai: {REPLY}" in out
    assert out.index("progress model finished") < out.index(f"tokens speak ai: {REPLY}")
    assert out[-2] == "parts {'messages': 2, 'updates': 6, 'custom': 2}"
    assert out[-1] == f"reply {REPLY}"


def test_watch_sees_the_nodes_the_package_test_expects(scripted, capsys):
    lab, _ = _run(LAB, capsys)
    graph = build_v5_stream(model=FakeChatModel(route="orders", reply=REPLY))
    seen = lab["watch"](graph, {"ticket": "Where is order DF-1002?"}, {"configurable": {"thread_id": "t"}})
    out = capsys.readouterr().out.splitlines()
    assert {line.split()[1] for line in out if line.startswith("node ")} == set(NODES)
    assert seen["counts"]["updates"] == 6 and seen["counts"]["custom"] == 2
    assert seen["reply"] == REPLY


def test_break_values_lane_has_no_tokens(scripted, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, MODES, 'stream_mode=["updates", "values", "custom"]')
    _, out = _run(broken, capsys)
    assert not [line for line in out if line.startswith("tokens ")]
    values = [line for line in out if line.startswith("values keys ")]
    assert len(values) >= 4
    assert "'reply'" in values[-1] and "'route'" in values[-1]
    assert out[-2].startswith("parts {'values': ")
