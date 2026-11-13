"""Lab 06.08.06 (17.5), planner, slow_lookup and build_timeout typed by the student; the break hands add_node the plain
def. The fixture model plans and summarizes; its usage metadata makes the spend cap count tokens."""

import asyncio
import runpy
from pathlib import Path

import pytest

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.runaway import build_graceful, build_timeout_demo
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_08_06_cap_a_runaway.py"
ASYNC_NODE = "        slow_lookup,\n"
SYNC_NODE = "        slow_lookup_sync,\n"
TICKET = "Where is order DF-1002? Tracking still says in transit."
BUDGET_LINE = "The desk could not finish this request within its step budget."


@pytest.fixture
def fixture_model(monkeypatch):
    usage = {"input_tokens": 100, "output_tokens": 150, "total_tokens": 250}
    model = FakeChatModel(reply="Look up the order next.", usage_metadata=usage)
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    return model


def _stops(out: list[str]) -> dict[str, str]:
    return {line.split()[1]: line.split(" | ", 1)[1] for line in out if line.startswith("stopped_by ")}


def test_lab_logs_four_brakes(fixture_model, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "model FakeChatModel None"
    assert out[1] == "langchain-core 1.6.2" and out[2] == "langgraph 1.2.11"
    assert out[3] == "default_recursion_limit 10007"
    stops = _stops(out)
    assert list(stops) == ["recursion_limit", "remaining_steps", "timeout", "spend_cap"]
    assert stops["recursion_limit"].startswith("Recursion limit of 8 reached without hitting a stop condition.")
    assert stops["remaining_steps"] == f"steps 6 done True reply {BUDGET_LINE}"
    assert stops["timeout"].startswith("NodeTimeoutError after ")
    assert stops["timeout"].endswith("lookup {'found': False, 'reason': 'lookup timed out after retries'}")
    assert 2.0 <= float(stops["timeout"].split()[2]) < 6.0
    detail = out[out.index(next(line for line in out if line.startswith("stopped_by timeout"))) + 1]
    assert detail.startswith("timeout_detail Node 'slow_lookup' exceeded its run timeout of 1.000s (elapsed: ")
    assert stops["spend_cap"] == (
        "Stopped: spent 750 tokens over a budget of 600 after 3 model calls. counted from usage_metadata"
    )


def test_typed_brakes_match_the_package(fixture_model):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    cap = {"recursion_limit": 8}
    mine = lab["build_planner_loop"]().invoke({"ticket": TICKET}, cap, context=DeskContext(model=fixture_model))
    package = build_graceful(model=fixture_model).invoke({"ticket": TICKET, "done": False}, cap)
    assert (mine["steps"], mine["done"], mine["reply"]) == (package["steps"], package["done"], package["reply"])
    mine_timeout = asyncio.run(lab["build_timeout"]().ainvoke({"ticket": TICKET}))
    package_timeout = asyncio.run(build_timeout_demo().ainvoke({"ticket": TICKET}))
    stable = ("lookup", "timeout_error")
    assert {k: mine_timeout[k] for k in stable} == {k: package_timeout[k] for k in stable}
    assert mine_timeout["timeout_detail"].split(" (elapsed")[0] == package_timeout["timeout_detail"].split(" (elapsed")[0]


def test_break_sync_node_fails_at_compile(fixture_model, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, ASYNC_NODE, SYNC_NODE)
    with pytest.raises(ValueError) as caught:
        runpy.run_path(str(broken), run_name="__main__")
    assert str(caught.value) == (
        "Node timeouts are only supported for async nodes because sync Python execution cannot be safely "
        "cancelled in-process. Node 'slow_lookup' is sync."
    )
    assert list(_stops(capsys.readouterr().out.splitlines())) == ["recursion_limit", "remaining_steps"]
