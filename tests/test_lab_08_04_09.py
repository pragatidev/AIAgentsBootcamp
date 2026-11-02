"""Lab 08.04.09 (25.9), trace_totals typed by the student. A scripted LangChain chat model (so the tracer and the meter
see real model calls) and fixed passages stand in for the real ones here, and only here."""

import runpy
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

import config
from dataflow.graphs import rag_graph as G
from dataflow.ops import tracer
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "08_04_09_trace_cost_latency.py"
USAGE = {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
PASSAGES = [
    {"text": "Agent (Level 1): Approve refunds under 30 days.", "source": "dataflow/knowledge_base/internal_operations/support_operations/customer_support_procedures.markdown", "folder": "internal_operations", "score": 0.4, "heading_path": "6.1"},
    {"text": "Returns are allowed within 30 days.", "source": "dataflow/wiki/return_policy.md", "folder": "wiki", "score": 0.6, "heading_path": ""},
    {"text": "Standard shipping is five business days.", "source": "dataflow/wiki/shipping.md", "folder": "wiki", "score": 0.9, "heading_path": ""},
]
PAYLOADS = {"Route": {"route": "retrieve"}, "Grade": {"label": "keep", "reason": "fixture"}}


class TracedChat(BaseChatModel):
    """Every call, structured or not, is one real chat model call with usage, so callbacks fire."""

    @property
    def _llm_type(self) -> str:
        return "traced-fixture"

    def _generate(self, messages: list[Any], stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="An agent approves refunds under 30 days.", usage_metadata=USAGE))])

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        return self | RunnableLambda(lambda _message: schema.model_validate(PAYLOADS[schema.__name__]))


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: TracedChat())
    monkeypatch.setattr(G, "get_index", lambda *a, **k: object())
    monkeypatch.setattr(G, "search", lambda *a, **k: [dict(p) for p in PASSAGES])
    monkeypatch.setattr(tracer, "_ensure_traces_dir", lambda: tmp_path)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)


def _out(path, capsys):
    namespace = runpy.run_path(str(path), run_name="__main__")
    return namespace, capsys.readouterr().out.splitlines()


def test_the_trace_adds_up(capsys):
    _, out = _out(LAB, capsys)
    assert "model_calls 5 meter_counted 5" in out
    assert "calls_match_meter True" in out
    assert "tokens {'input': 50, 'output': 10, 'total': 60}" in out
    assert "cost n/a (local model, no per-token price)" in out
    assert "grade_off model_calls 2 tokens 24" in out and "calls_the_grader_added 3" in out
    assert sum(1 for line in out if line.startswith("model_call ")) == 5


def test_typed_totals_match_the_module(capsys):
    lab, out = _out(LAB, capsys)
    traces = sorted(Path(tracer._ensure_traces_dir()).glob("*.jsonl"))
    assert traces
    for path in traces:
        assert lab["trace_totals"](path) == tracer.trace_totals(path)


def test_the_break_counts_every_span(tmp_path, capsys):
    old = '        if span.get("kind") == "chat_model":\n            model_calls += 1\n'
    new = '        model_calls += 1\n        if span.get("kind") == "chat_model":\n'
    _, out = _out(lab_copy(LAB, tmp_path, old, new), capsys)
    assert "calls_match_meter False" in out
