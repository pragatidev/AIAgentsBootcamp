"""Lab 06.07.02 (16.2), ParallelState and build_parallel typed by the student; the gather broken by taking the reducer
off; the defer cell moved from 06_08_04. The fixture model stands in for qwen3:8b."""

import runpy
from pathlib import Path
from typing import get_type_hints

import pytest
from langgraph.errors import InvalidUpdateError

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.v6_parallel import ParallelState, build_v6_parallel
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_07_02_two_lookups_in_parallel.py"
REDUCER = "    results: Annotated[list, operator.add]\n"
REPLY = "Order DF-1001 is delivered. The return window is 30 days."
TICKET = "Hi, I want to return order DF-1001. The desk lamp is unused. Can I get a refund?"


@pytest.fixture
def fixture_model(monkeypatch):
    model = FakeChatModel(route="orders", reply=REPLY)
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    return model


def _edges(graph):
    return {(e.source, e.target, e.conditional) for e in graph.get_graph().edges}


def test_lab_runs_both_lookups_in_one_step(fixture_model, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "model FakeChatModel None"
    assert out[1] == "langchain-core 1.6.2" and out[2] == "langgraph 1.2.11"
    results = [line for line in out if line.startswith("result ")]
    assert len(results) == 2
    assert "'source': 'lookup'" in results[0] and "'order_id': 'DF-1001'" in results[0]
    assert "'source': 'policy'" in results[1] and "wiki/return_policy.md" in results[1]
    assert f"reply {REPLY}" in out
    steps = out[out.index("history_oldest_first 5") + 1 :][:5]
    assert steps == [
        "step -1 next ['__start__']",
        "step 0 next ['classify']",
        "step 1 next ['lookup', 'policy_search']",
        "step 2 next ['draft_reply']",
        "step 3 next []",
    ]
    assert out[-2].startswith("summarize_runs defer False 2 ")
    assert out[-1].startswith("summarize_runs defer True 1 ")


def test_typed_graph_matches_the_package(fixture_model):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    assert get_type_hints(lab["ParallelState"], include_extras=True) == get_type_hints(ParallelState, include_extras=True)
    mine, package = lab["build_parallel"](), build_v6_parallel(model=fixture_model)
    assert set(mine.get_graph().nodes) == set(package.get_graph().nodes)
    assert _edges(mine) == _edges(package)
    thread = {"configurable": {"thread_id": "test-16-2"}}
    assert mine.invoke({"ticket": TICKET}, thread, context=DeskContext(model=fixture_model)) == package.invoke(
        {"ticket": TICKET}, thread
    )


def test_break_no_reducer_raises_invalid_update(fixture_model, tmp_path):
    broken = lab_copy_dataflow(LAB, tmp_path, REDUCER, "    results: list\n")
    with pytest.raises(InvalidUpdateError) as caught:
        runpy.run_path(str(broken), run_name="__main__")
    assert str(caught.value).splitlines()[0] == (
        "At key 'results': Can receive only one value per step. Use an Annotated key to handle multiple values."
    )
