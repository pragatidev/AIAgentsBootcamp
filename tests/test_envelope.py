"""DeskContext lives in dataflow/envelope.py, a module with no graph in it, and the old import path gives the same class."""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GRAPH_MODULES = ["v1_triage", "billing_subgraph", "durable", "messages", "plan_execute", "rag_graph", "rag_tool_cycle", "runaway", "trim"]


def test_both_import_paths_give_one_class():
    from dataflow.envelope import DeskContext as neutral
    from dataflow.graphs.v1_triage import DeskContext as from_the_graph_file

    assert neutral is from_the_graph_file
    ctx = neutral()
    assert (ctx.model, ctx.customer_id, ctx.actor_id, ctx.user_id) == (None, "anon", "anon", "")
    assert neutral(actor_id="desk-lead").actor_id == "desk-lead"


@pytest.mark.parametrize("name", GRAPH_MODULES)
def test_every_graph_that_imported_it_still_has_the_same_class(name):
    from dataflow.envelope import DeskContext

    assert importlib.import_module(f"dataflow.graphs.{name}").DeskContext is DeskContext


def test_the_envelope_imports_no_agent_and_no_graph():
    code = (
        "import sys, dataflow.envelope; "
        "print(sorted(m for m in sys.modules if m.split('.')[0] in ('langgraph', 'langchain', 'langchain_core') or m.startswith('dataflow.graphs')))"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "[]"


def test_v1_triage_lines_that_recorded_lectures_show_did_not_move():
    lines = (ROOT / "dataflow" / "graphs" / "v1_triage.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 132
    assert lines[22] == "CLASSIFY_SYSTEM = ("
    assert lines[40] == "class RouteDecision(BaseModel):"
    assert lines[41] == '    route: Literal["orders", "policy", "escalate"] = Field('
    assert lines[67] == "    structured = chat.with_structured_output(RouteDecision)"
