"""Lab 06.02.06 (11.6), classify_command and build_command typed by the student. A scripted classifier stands in for
the real model here, and only here."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.v2_command import build_v2_command
from dataflow.graphs.v2_route import build_v2_route
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_02_06_command_vs_edge.py"
HINT = ') -> Command[Literal["orders_desk", "policy_desk", "escalate_desk"]]:\n'
TICKETS = {"orders": "Where is order DF-1001?", "policy": "What is your return window?", "escalate": "I want a manager now."}


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="orders"))


def _command_drawing(out):
    return out[out.index("command_drawing") + 1 :]


def test_lab_prints_both_roads_and_both_drawings(scripted, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "edge_route orders edge_reply Order DF-1002 is in_transit. Item: USB-C hub." in out
    assert "command_route orders command_reply Order DF-1002 is in_transit. Item: USB-C hub." in out
    assert "same_road True" in out
    drawing = _command_drawing(out)
    for desk in ("orders_desk", "policy_desk", "escalate_desk"):
        assert f"\tclassify -.-> {desk};" in drawing
    assert "\tclassify --> __end__;" not in drawing


def test_same_ticket_same_road_through_edge_and_command(scripted):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    for route, text in TICKETS.items():
        model = FakeChatModel(route=route)
        edge = build_v2_route(model=model).invoke({"ticket": text})
        mine = lab["build_command"]().invoke({"ticket": text}, context=DeskContext(model=model))
        package = build_v2_command(model=model).invoke({"ticket": text})
        assert edge["route"] == mine["route"] == package["route"] == route
        assert edge["reply"] == mine["reply"] == package["reply"]
    mine = lab["build_command"]().get_graph()
    package = build_v2_command(model=FakeChatModel()).get_graph()
    assert {(e.source, e.target, e.conditional) for e in mine.edges} == {(e.source, e.target, e.conditional) for e in package.edges}


def test_break_no_declared_roads_runs_but_the_drawing_loses_them(scripted, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, HINT, ") -> Command:\n")
    runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "same_road True" in out
    drawing = _command_drawing(out)
    assert "\tclassify --> __end__;" in drawing
    assert not any(line.startswith("\tclassify -.->") for line in drawing)
