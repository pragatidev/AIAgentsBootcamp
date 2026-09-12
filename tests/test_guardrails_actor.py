"""11.2 actor id on a mutating call. Pytest stays green with no Ollama."""

from dataflow.graphs.v1_triage import DeskContext
from dataflow.ops import tracer
from dataflow.tools.refund import build_confirm_graph, resume_confirm


def test_logged_actor_equals_invoking_user(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "refunds.jsonl"))
    graph = build_confirm_graph()
    cfg = {"configurable": {"thread_id": "actor-test"}}
    ctx = DeskContext(user_id="reviewer-1")
    graph.invoke(
        {
            "order_id": "DF-1001",
            "amount": 1.0,
            "reason": "test",
            "actor": "",
        },
        cfg,
        context=ctx,
    )
    resume_confirm(graph, cfg, {"action": "approve"})
    line = tracer.last_actor_line or ""
    assert "actor=reviewer-1" in line, line
    assert not line.startswith("actor=admin")
