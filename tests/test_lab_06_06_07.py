"""Lab 06.06.07 (15.2, second half), stream_tool_cycle typed by the student. Scripted models stand in for the real one
here, and only here: ScriptedToolChatModel sends the call whole in one piece (as qwen3:8b on Ollama does) and
PiecewiseToolChatModel sends the id and name, then the arguments in pieces (as a provider that streams arguments
does). The tests assert the finished call, never the shape of a piece beyond what the scripted model sends, so they
hold on both sides of the langchain-core change to streamed tool calls."""

import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from dataflow.graphs.v2_tools import build_v2_tools
from tests.fixtures.fake_model import ScriptedToolChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow
from tests.fixtures.lg_r2 import PiecewiseToolChatModel

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_06_07_stream_the_tool_cycle.py"
MODES = 'stream_mode=["messages", "updates"]'
CALL = '[["lookup_order", {"order_id": "DF-1002"}, "c1"]]'


def _script():
    call = {"name": "lookup_order", "args": {"order_id": "DF-1002"}, "id": "c1", "type": "tool_call"}
    return [AIMessage(content="", tool_calls=[call]), AIMessage(content="DF-1002 is in transit.")]


def _use(monkeypatch, cls):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: cls(script=_script()))


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


@pytest.mark.parametrize("cls", [ScriptedToolChatModel, PiecewiseToolChatModel])
def test_the_finished_call_is_the_same_from_pieces_and_from_the_update(monkeypatch, capsys, cls):
    _use(monkeypatch, cls)
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    assert out[-3:] == [f"call_from_pieces {CALL}", f"call_from_update {CALL}", "same_call True"]
    assert 'finished [["lookup_order", {"order_id": "DF-1002"}]]' in out
    assert any(line.startswith('tool result lookup_order {"found": true, "order_id": "DF-1002"') for line in out)
    assert "answer DF-1002 is in transit." in out
    pieces = [line for line in out if line.startswith("piece ")]
    assert pieces[0].startswith("piece 1 id c1 name lookup_order args ")
    assert out.index(pieces[-1]) < out.index('finished [["lookup_order", {"order_id": "DF-1002"}]]')


def test_one_piece_and_many_pieces(monkeypatch, capsys):
    _use(monkeypatch, ScriptedToolChatModel)
    _, one = _run(LAB, capsys)
    _use(monkeypatch, PiecewiseToolChatModel)
    _, many = _run(LAB, capsys)
    assert [line for line in one if line.startswith("piece ")] == [
        """piece 1 id c1 name lookup_order args '{"order_id": "DF-1002"}'"""
    ]
    many_pieces = [line for line in many if line.startswith("piece ")]
    assert many_pieces[0] == "piece 1 id c1 name lookup_order args ''"
    assert all(" id None name None " in line for line in many_pieces[1:])
    assert len(many_pieces) == 4


def test_typed_loop_watches_the_package_cycle(monkeypatch, capsys):
    _use(monkeypatch, PiecewiseToolChatModel)
    lab, _ = _run(LAB, capsys)
    assembled, finished = lab["stream_tool_cycle"](build_v2_tools(model=PiecewiseToolChatModel(script=_script())), "Where is DF-1002?")
    assert [(c["name"], c["args"]) for c in assembled] == [("lookup_order", {"order_id": "DF-1002"})]
    assert [(c["name"], c["args"], c["id"]) for c in assembled] == [(c["name"], c["args"], c["id"]) for c in finished]


def test_break_no_messages_lane_no_pieces(monkeypatch, tmp_path, capsys):
    _use(monkeypatch, PiecewiseToolChatModel)
    broken = lab_copy_dataflow(LAB, tmp_path, MODES, 'stream_mode=["updates"]')
    _, out = _run(broken, capsys)
    assert not [line for line in out if line.startswith("piece ")]
    assert "pieces 0 text_tokens 0 quiet_chunks 0" in out
    assert 'finished [["lookup_order", {"order_id": "DF-1002"}]]' in out
    assert out[-3:] == ["call_from_pieces []", f"call_from_update {CALL}", "same_call False"]
