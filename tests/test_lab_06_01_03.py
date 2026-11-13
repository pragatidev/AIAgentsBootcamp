"""Lab 06.01.03 (10.3), TriageState and build_triage typed by the student. A scripted classifier stands in for the
real model here, and only here."""

import runpy
from pathlib import Path
from typing import get_type_hints

import pytest

import config
from dataflow.graphs.v1_triage import TriageState as PackageState
from dataflow.graphs.v1_triage import build_v1_triage
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_01_03_build_triage_graph.py"
END_EDGE = '    builder.add_edge("reply", END)\n'
LOOKUP_EDGE = '    builder.add_edge("lookup", "reply")\n'


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="orders"))


def _edges(graph):
    return {(e.source, e.target, e.conditional) for e in graph.get_graph().edges}


def test_lab_prints_the_graph_and_the_ticket(scripted, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "state_keys ['ticket', 'route', 'order', 'reply']" in out
    assert "nodes ['__start__', 'classify', 'lookup', 'reply', '__end__']" in out
    for edge in ("\t__start__ --> classify;", "\tclassify --> lookup;", "\tlookup --> reply;", "\treply --> __end__;"):
        assert edge in out
    assert out[-3:] == [
        "route orders",
        "order {'found': True, 'order_id': 'DF-1002', 'item': 'USB-C hub', 'status': 'in_transit', "
        "'days_since_delivery': None, 'amount': 29.99, 'customer_id': 'C-2002', 'region': 'EU'}",
        "reply Order DF-1002 is in_transit. Item: USB-C hub.",
    ]


def test_typed_graph_matches_the_package(scripted):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    assert get_type_hints(lab["TriageState"]) == get_type_hints(PackageState)
    assert lab["TriageState"].__total__ is False
    mine = lab["build_triage"](model=FakeChatModel(route="policy"))
    package = build_v1_triage(model=FakeChatModel(route="policy"))
    assert set(mine.get_graph().nodes) == set(package.get_graph().nodes)
    assert _edges(mine) == _edges(package)
    ticket = {"ticket": "Where is order DF-9999?"}
    assert mine.invoke(ticket) == package.invoke(ticket)


def test_break_one_no_edge_to_end_still_compiles_and_runs(scripted, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, END_EDGE, "")
    lab = runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "reply Order DF-1002 is in_transit. Item: USB-C hub."
    assert "\treply --> __end__;" in out
    graph = lab["build_triage"](model=FakeChatModel(route="orders"))
    assert ("reply", "__end__", False) in _edges(graph)


def test_break_two_misspelt_node_fails_at_compile(scripted, tmp_path):
    broken = lab_copy_dataflow(LAB, tmp_path, LOOKUP_EDGE, '    builder.add_edge("lookup", "replly")\n')
    with pytest.raises(ValueError, match="Found edge ending at unknown node `replly`"):
        runpy.run_path(str(broken), run_name="__main__")
