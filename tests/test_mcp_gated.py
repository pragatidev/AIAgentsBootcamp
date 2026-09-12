"""13.1.7 gated MCP refund. Fixture model, in-process server, temp ledger."""

from dataflow.mcp.bind import bind_mcp_tools, close_mcp
from dataflow.mcp.gated import build_gated_mcp, resume_gated
from dataflow.tools import refund as refund_mod
from tests.fixtures.fake_model import FakeChatModel


def _tools():
    return bind_mcp_tools()


def test_deny_writes_nothing(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    try:
        tools = _tools()
        graph = build_gated_mcp(model=FakeChatModel(), tools=tools)
        cfg = {"configurable": {"thread_id": "mcp-deny"}}
        graph.invoke(
            {
                "order_id": "DF-1001",
                "amount": 49.0,
                "reason": "unused lamp",
            },
            cfg,
        )
        state = graph.get_state(cfg)
        assert state.interrupts
        payload = state.interrupts[0].value
        assert payload["action"] == "refund"
        assert payload["order_id"] == "DF-1001"
        done = resume_gated(graph, cfg, False)
        assert done.get("refund", {}).get("refunded") is False
        assert refund_mod.read_refunds() == []
        assert not path.exists()
    finally:
        close_mcp()


def test_approve_writes_one_row(tmp_path, monkeypatch):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    try:
        tools = _tools()
        graph = build_gated_mcp(model=FakeChatModel(), tools=tools)
        cfg = {"configurable": {"thread_id": "mcp-approve"}}
        graph.invoke(
            {
                "order_id": "DF-1001",
                "amount": 49.0,
                "reason": "unused lamp",
            },
            cfg,
        )
        assert refund_mod.read_refunds() == []
        done = resume_gated(graph, cfg, True)
        assert done.get("refund", {}).get("refunded") is True
        rows = refund_mod.read_refunds()
        assert len(rows) == 1
        assert rows[0]["order_id"] == "DF-1001"
        assert rows[0]["amount"] == 49.0
        assert path.is_file()
    finally:
        close_mcp()
