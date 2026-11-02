"""Tokens, model calls and step times per question (25.9). Hand-written spans and fixture pipelines, here only. No Ollama."""

import json

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import config
from dataflow.ops.tracer import trace_totals
from eval.runners import rag_metrics as M


def test_trace_totals_sums_tokens(tmp_path):
    path = tmp_path / "trace.jsonl"
    spans = [
        {"kind": "chain", "name": "retrieve", "duration_ms": 12.5},
        {"kind": "chat_model", "name": "ChatOllama", "duration_ms": 900, "tokens": {"input": 100, "output": 20, "total": 120}},
        {"kind": "chat_model", "name": "ChatOllama", "duration_ms": 800, "tokens": {"input": 90, "output": 10, "total": 100}},
        {"kind": "chain", "name": "grade", "duration_ms": 1700.0},
        {"kind": "chain", "name": "grade", "duration_ms": 300.0},
        {"kind": "tool", "name": "retrieve", "duration_ms": 3.0},
    ]
    path.write_text("\n".join(json.dumps(s) for s in spans) + "\n", encoding="utf-8")
    assert trace_totals(path) == {
        "tokens": {"input": 190, "output": 30, "total": 220},
        "model_calls": 2,
        "step_ms": {"retrieve": 12.5, "grade": 2000.0},
    }


def test_the_meter_counts_calls_and_tokens_inside_its_block():
    usage = {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}
    chat = GenericFakeChatModel(messages=iter([AIMessage(content="one", usage_metadata=usage), AIMessage(content="two", usage_metadata=usage)]))
    with M.meter() as used:
        chat.invoke("a")
        chat.invoke("b")
    chat2 = GenericFakeChatModel(messages=iter([AIMessage(content="three", usage_metadata=usage)]))
    chat2.invoke("outside the block")
    assert used.model_calls == 2 and used.tokens == 20


def test_metrics_table_has_tokens_and_calls_columns():
    def naive(question):
        return {"answer": "Returns are allowed within 30 days.", "sources": [], "passages": [], "route": "naive", "tokens": 120, "model_calls": 1}

    def agentic(question):
        return {"answer": "Returns are allowed within 30 days.", "sources": [], "passages": [], "route": "retrieve", "tokens": 480, "model_calls": 5}

    report = M.run_metrics(judge=lambda a, p, model=None: 1, naive_fn=naive, agentic_fn=agentic)
    table = M.render(report)
    header, naive_line, agentic_line = table.splitlines()[:3]
    assert header.endswith("fluent_misses  tokens_per_q  calls_per_q")
    assert naive_line.split()[-2:] == ["120", "1.0"]
    assert agentic_line.split()[-2:] == ["480", "5.0"]
    assert "per_row" in table


def test_cost_is_na_without_prices(monkeypatch):
    monkeypatch.setattr(config, "PRICE_PER_MTOK_IN", None)
    monkeypatch.setattr(config, "PRICE_PER_MTOK_OUT", None)
    assert M.cost_line(1000, 100) == "cost n/a (local model, no per-token price)"
    monkeypatch.setattr(config, "PRICE_PER_MTOK_IN", 2.0)
    monkeypatch.setattr(config, "PRICE_PER_MTOK_OUT", 10.0)
    assert M.cost_line(1_000_000, 100_000) == "cost 3.000000 at your prices (2.0 in, 10.0 out per million tokens)"
