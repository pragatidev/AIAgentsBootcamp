"""Lab 06.03.04 (12.4), FixedState and build_fixed typed by the student; the collision planted by taking the reducer
off. No model is called."""

import runpy
from pathlib import Path
from typing import get_type_hints

import pytest
from langgraph.errors import InvalidUpdateError

from dataflow.graphs.collision import ReducedState, build_collision, build_collision_fixed
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_03_04_plant_a_collision.py"
REDUCER = "    log: Annotated[list[str], operator.add]\n"
MESSAGE = (
    "At key 'log': Can receive only one value per step. Use an Annotated key to handle multiple values."
)


def _edges(graph):
    return {(e.source, e.target, e.conditional) for e in graph.get_graph().edges}


def test_lab_prints_both_log_lines(capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "model none: this run calls no model"
    assert "\t__start__ --> write_a;" in out and "\t__start__ --> write_b;" in out
    assert "log_channel BinaryOperatorAggregate" in out
    assert out[-3:] == ["log_lines 2", "log orders looked up", "log policy read"]


def test_typed_graph_matches_the_package():
    lab = runpy.run_path(str(LAB), run_name="__main__")
    assert get_type_hints(lab["FixedState"], include_extras=True) == get_type_hints(ReducedState, include_extras=True)
    mine, package = lab["build_fixed"](), build_collision_fixed()
    assert set(mine.get_graph().nodes) == set(package.get_graph().nodes)
    assert _edges(mine) == _edges(package)
    start = {"ticket": "DF-1001", "log": []}
    assert mine.invoke(start) == package.invoke(start)


def test_break_no_reducer_raises_invalid_update(tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, REDUCER, "    log: list[str]\n")
    with pytest.raises(InvalidUpdateError) as caught:
        runpy.run_path(str(broken), run_name="__main__")
    assert str(caught.value).splitlines()[0] == MESSAGE
    assert "log_channel LastValue" in capsys.readouterr().out.splitlines()


def test_package_planted_graph_still_collides():
    with pytest.raises(InvalidUpdateError, match="Can receive only one value per step"):
        build_collision().invoke({"ticket": "DF-1001", "log": ""})
