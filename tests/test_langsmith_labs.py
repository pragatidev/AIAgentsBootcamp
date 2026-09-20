"""LangSmith labs. Pytest stays green with no key."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.graph import END, START, StateGraph

from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.ops.tracer import render_waterfall, traced_invoke
from dataflow.tracing import (
    callbacks_for_run,
    langsmith_key_present,
    langsmith_tracer_if_key,
    retrieve_span_name,
)
from eval.judges.langsmith_judge import (
    judge_answer,
    parse_score,
    score_three,
    three_samples,
)
from eval.langsmith_dataset import exact_source_or_refuse, example_outputs, load_named_rows
from tests.fixtures.fake_model import FakeChatModel

LOOKUP = "Where is order DF-1001?"


class ProbeState(TypedDict, total=False):
    text: str
    reply: str


def _clear_langsmith_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@pytest.fixture
def no_langsmith(monkeypatch):
    _clear_langsmith_env(monkeypatch)


def _probe_graph(model: Any):
    def chat_node(state: ProbeState, config: Any = None) -> dict[str, str]:
        message = model.invoke(state.get("text") or "", config)
        content = getattr(message, "content", message)
        return {"reply": str(content)}

    builder = StateGraph(ProbeState)
    builder.add_node("chat", chat_node)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)
    return builder.compile()


def test_callbacks_for_run_fallback_without_key(monkeypatch, capsys):
    _clear_langsmith_env(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    cbs = callbacks_for_run()
    names = [type(cb).__name__ for cb in cbs]
    assert "LocalTraceHandler" in names
    assert "LangChainTracer" not in names
    out = capsys.readouterr().out
    assert "fallback" in out
    assert langsmith_tracer_if_key() is None
    assert langsmith_key_present() is False


def test_config_tracing_callbacks_no_key_is_local_only(monkeypatch):
    _clear_langsmith_env(monkeypatch)
    import config

    names = [type(cb).__name__ for cb in config.tracing_callbacks()]
    assert names == ["LocalTraceHandler"]


def test_fixture_model_writes_local_trace(tmp_path, monkeypatch):
    _clear_langsmith_env(monkeypatch)
    import dataflow.ops.tracer as tracer_mod

    monkeypatch.setattr(tracer_mod, "TRACES_DIR", tmp_path)
    model = FakeListChatModel(responses=["looked up DF-1001"])
    graph = _probe_graph(model)
    out, path = traced_invoke(
        graph,
        {"text": LOOKUP},
        {"configurable": {"thread_id": "test-langsmith-local"}},
        run_name="probe",
    )
    assert path.is_file()
    raw = path.read_text(encoding="utf-8")
    assert raw.strip()
    kinds = [json.loads(line).get("kind") for line in raw.splitlines() if line.strip()]
    assert "chat_model" in kinds or "chain" in kinds
    assert out.get("reply") == "looked up DF-1001"
    text = render_waterfall(path)
    assert "probe" in text or "chat" in text


def test_retrieve_span_name_from_waterfall():
    sample = "run desk 10ms\n  chain retrieve 4ms\n  chain generate 3ms\n"
    assert retrieve_span_name(sample) == "retrieve"


def test_code_evaluator_skips_missing_reference():
    run = SimpleNamespace(outputs={"answer": "30 days", "sources": []})
    empty = SimpleNamespace(outputs=None, inputs={"id": "policy-shipping"})
    skipped = exact_source_or_refuse(run, empty)
    assert skipped["score"] is None
    assert "missing reference" in skipped["comment"]
    rows = load_named_rows(["policy-return"])
    filled = SimpleNamespace(
        outputs=example_outputs(rows[0]),
        inputs={"id": "policy-return"},
    )
    run2 = SimpleNamespace(
        outputs={
            "answer": "30 days from delivery",
            "sources": [{"source": "dataflow/wiki/return_policy.md"}],
        }
    )
    hit = exact_source_or_refuse(run2, filled)
    assert hit["score"] == 1


def test_judge_parse_and_fixture_scores():
    assert parse_score("1") == 1
    assert parse_score("0") == 0
    yes = judge_answer(
        "From return_policy.md: 30 days.",
        [{"source": "dataflow/wiki/return_policy.md", "text": "30 days"}],
        must_cite_file=False,
        model=FakeChatModel(reply="1"),
    )
    assert yes["score"] == 1
    no = judge_answer(
        "You have a ninety-day refund window from delivery.",
        [{"source": "dataflow/wiki/return_policy.md", "text": "30 days"}],
        must_cite_file=True,
        model=FakeChatModel(reply="0"),
    )
    assert no["score"] == 0
    samples = three_samples()
    assert [row["id"] for row in samples] == ["grounded", "fluent_wrong", "refuse"]
    scored = score_three(samples, must_cite_file=True, model=FakeChatModel(reply="0"))
    fluent = [row for row in scored if row["id"] == "fluent_wrong"][0]
    assert fluent["score"] == 0


def test_prompt_and_labels_files_exist():
    from config import ROOT

    prompt_path = ROOT / "prompts" / "dataflow_system.md"
    labels_path = ROOT / "eval" / "labels.jsonl"
    if not prompt_path.is_file() or not labels_path.is_file():
        pytest.skip("9.2 prompt and labels files")
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "passages" in prompt.lower()
    assert "\u2014" not in prompt
    labels = labels_path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in labels.splitlines() if line.strip()]
    assert len(rows) == 2
    values = {row.get("value") for row in rows}
    assert "grounded" in values
    assert "fluent_wrong" in values


def test_client_info_version():
    from src.paths import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1])
    if not os.environ.get("LANGSMITH_API_KEY", "").strip() and not os.environ.get(
        "LANGCHAIN_API_KEY", ""
    ).strip():
        pytest.skip("no langsmith key")
    from langsmith import Client

    info = Client().info
    version = getattr(info, "version", "") or ""
    assert version


def test_prompt_helpers_write_local_fallback(tmp_path, no_langsmith):
    prompts = pytest.importorskip("eval.langsmith_prompts")
    prompt_v1 = prompts.prompt_v1
    prompt_v2 = prompts.prompt_v2
    write_labels = prompts.write_labels
    write_local_prompt = prompts.write_local_prompt

    path = write_local_prompt(prompt_v1(), path=tmp_path / "dataflow_system.md")
    text = path.read_text(encoding="utf-8")
    assert "say you do not have it." in text
    v2 = prompt_v2()
    assert "knowledge base" in v2
    labels = write_labels(
        [
            {"id": "grounded", "key": "label", "value": "grounded"},
            {"id": "fluent_wrong", "key": "label", "value": "fluent_wrong"},
        ],
        path=tmp_path / "labels.jsonl",
    )
    rows = [
        json.loads(line)
        for line in labels.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    assert rows[0]["value"] == "grounded"
    assert rows[1]["value"] == "fluent_wrong"


def test_studio_replay_edit_cites_chunk(tmp_path, monkeypatch, no_langsmith):
    from langgraph.checkpoint.memory import InMemorySaver

    monkeypatch.setattr(
        "dataflow.graphs.rag_graph.retrieve_passages",
        lambda *args, **kwargs: [
            {
                "source": "dataflow/wiki/return_policy.md",
                "text": "The customer return window is 30 days from delivery.",
                "folder": "wiki",
            }
        ],
    )
    model = FakeChatModel(
        route="retrieve",
        reply=[
            "The customer return window is 30 days from delivery.",
            "The packing slip window is fourteen days.",
        ],
    )
    graph = build_rag_graph(
        model=model, grade_enabled=False, cite_node=None, checkpointer=None
    )
    cfg = {"configurable": {"thread_id": "test-27-5"}}
    history = []
    try:
        history = list(graph.get_state_history(cfg))
    except Exception:
        history = []
    assert len(history) == 0

    saver = InMemorySaver()
    graph2 = build_rag_graph(
        model=model,
        grade_enabled=False,
        cite_node=None,
        checkpointer=saver,
    )
    graph2.invoke(
        {"question": "Can I get a ninety-day refund on an unused lamp?"},
        cfg,
    )
    history2 = list(graph2.get_state_history(cfg))
    assert len(history2) > 0
    edited = {
        "source": "edited-chunk",
        "text": "EDITED CHUNK: the packing slip window is fourteen days.",
        "folder": "wiki",
    }
    graph2.update_state(
        cfg,
        {"passages": [edited], "graded": [edited]},
        as_node="retrieve",
    )
    out3 = graph2.invoke(None, cfg)
    answer = str(out3.get("answer") or out3.get("reply") or "")
    assert "fourteen" in answer.lower()
