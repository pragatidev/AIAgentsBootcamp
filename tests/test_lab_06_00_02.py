"""Lab 06.00.02 (9.2), what create_agent is made of. A scripted tool model stands in for the real one here, and only
here; the lab never calls it."""

import ast
import runpy
from importlib.metadata import version
from pathlib import Path

import pytest

import config
from tests.fixtures.fake_model import FakeToolModel

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_00_02_what_create_agent_is_made_of.py"


@pytest.fixture
def run(monkeypatch, capsys):
    model = FakeToolModel(script=[])
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: model)
    lab = runpy.run_path(str(LAB), run_name="__main__")
    return lab, model, capsys.readouterr().out.splitlines()


def test_printed_lines(run):
    _, _, out = run
    assert out[0] == "model FakeToolModel None"
    assert out[1:3] == [f"langchain-core {version('langchain-core')}", f"langgraph {version('langgraph')}"]
    assert "desk_type langgraph.graph.state CompiledStateGraph" in out
    assert "is_compiled_state_graph True" in out
    assert "nodes ['__start__', 'model', 'tools', '__end__']" in out
    for edge in ("\t__start__ --> model;", "\tmodel -.-> __end__;", "\tmodel -.-> tools;", "\ttools -.-> model;"):
        assert edge in out
    assert "package_desk_type langgraph.graph.state CompiledStateGraph" in out
    assert (
        "package_desk_nodes ['__start__', 'model', 'tools', 'HumanInTheLoopMiddleware.after_model', "
        "'ToolCallLimitMiddleware.after_model', '__end__']"
    ) in out
    declared = [line for line in out if line.startswith("create_deep_agent returns ")]
    assert len(declared) == 1 and declared[0].startswith("create_deep_agent returns langgraph.graph.state.CompiledStateGraph[")
    assert out[-1] == "same_class True"


def test_no_model_call_no_deep_agent_no_other_framework(run):
    _, model, _ = run
    assert model._i == 0
    imported = []
    for node in ast.walk(ast.parse(LAB.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    tops = {name.split(".")[0] for name in imported}
    assert tops <= {"importlib", "inspect", "pathlib", "sys", "typing", "deepagents", "langchain", "langgraph", "config", "techcorp"}
    assert "create_deep_agent(" not in LAB.read_text(encoding="utf-8")
