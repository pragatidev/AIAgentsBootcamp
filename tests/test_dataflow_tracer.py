"""6.10 local tracer and langgraph.json. Pytest stays green with no key."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, TypedDict

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.ops import tracer as tracer_mod
from dataflow.ops.tracer import (
    build_failing_carrier_graph,
    render_waterfall,
    traced_invoke,
)
from dataflow.tools.flaky import reset_flaky, set_always_fail
from tests.fixtures.fake_model import FakeChatModel

ROOT = Path(__file__).resolve().parents[1]
LOOKUP_TICKET = "Where is order DF-1001?"


class ProbeState(TypedDict, total=False):
    text: str
    reply: str


def _thread(name: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": name}}


def _probe_graph(model: Any):
    def chat_node(state: ProbeState, config: RunnableConfig) -> dict[str, str]:
        message = model.invoke(state.get("text") or "", config)
        content = getattr(message, "content", message)
        return {"reply": str(content)}

    builder = StateGraph(ProbeState)
    builder.add_node("chat", chat_node)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)
    return builder.compile()


def test_trace_written(tmp_path, monkeypatch):
    monkeypatch.setattr(tracer_mod, "TRACES_DIR", tmp_path)
    model = FakeListChatModel(responses=["looked up DF-1001"])
    graph = _probe_graph(model)
    out, path = traced_invoke(
        graph,
        {"text": LOOKUP_TICKET},
        _thread("test-16-written"),
        run_name="probe",
    )
    assert path.is_file()
    raw = path.read_text(encoding="utf-8")
    assert raw.strip()
    kinds = [json.loads(line).get("kind") for line in raw.splitlines() if line.strip()]
    assert "chat_model" in kinds
    assert out.get("reply") == "looked up DF-1001"
    assert "trace" not in (out or {})


def test_tool_error_span_marked(tmp_path, monkeypatch):
    monkeypatch.setattr(tracer_mod, "TRACES_DIR", tmp_path)
    reset_flaky()
    set_always_fail(True)
    graph = build_failing_carrier_graph()
    try:
        traced_invoke(
            graph,
            {"ticket": "Where is order DF-1002? Tracking still says in transit."},
            _thread("test-16-fail"),
            run_name="fail",
        )
    except Exception:
        pass
    path = tracer_mod.last_trace_path
    assert path is not None
    assert path.is_file()
    text = render_waterfall(path)
    assert "FAIL" in text
    assert "CarrierTimeout" in text


def test_trace_never_touches_state(tmp_path, monkeypatch):
    monkeypatch.setattr(tracer_mod, "TRACES_DIR", tmp_path)
    graph = build_v4_hitl(model=FakeChatModel(route="lookup"))
    out, path = traced_invoke(
        graph,
        {"ticket": LOOKUP_TICKET},
        _thread("test-16-state"),
        run_name="desk",
    )
    assert path.is_file()
    keys = set((out or {}).keys())
    banned = {
        "trace",
        "traces",
        "trace_id",
        "trace_path",
        "spans",
        "span",
        "run_id",
        "waterfall",
        "callbacks",
    }
    assert keys.isdisjoint(banned)
    blob = json.dumps(out, ensure_ascii=True, default=str)
    assert "trace_path" not in blob
    assert out.get("route") == "lookup"


def test_langgraph_json_lists_two_graphs():
    path = ROOT / "langgraph.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    graphs = spec.get("graphs") or {}
    assert "desk" in graphs
    assert "team" in graphs
    assert graphs["desk"] == "./dataflow/graphs/v4_hitl.py:graph"
    assert graphs["team"] == "./dataflow/graphs/v7_supervisor.py:graph"
    for ref in graphs.values():
        module_path, attr = str(ref).split(":")
        rel = module_path.replace("\\", "/").lstrip("./")
        if rel.endswith(".py"):
            rel = rel[:-3]
        mod_name = rel.replace("/", ".")
        mod = importlib.import_module(mod_name)
        assert hasattr(mod, attr)
        assert getattr(mod, attr) is not None
