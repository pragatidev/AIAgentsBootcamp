"""TechCorp desk. Fixture model. Pytest stays green with no live call."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from techcorp.agent.context import DeskContext
from techcorp.agent.desk import DEFAULT_MIDDLEWARE, build_techcorp_desk, run_ticket
from techcorp.agent.schemas import TicketClass
from techcorp.tools import accounts as accounts_mod
from tests.fixtures.fake_model import FakeChatModel, FakeToolModel


def _audit(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts_mod, "AUDIT_PATH", path)
    return path


def _reset_script(user_id: str = "E-4101") -> list:
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "reset_password",
                    "args": {"user_id": user_id},
                    "id": "call_reset",
                    "type": "tool_call",
                }
            ],
        ),
        "echo_tool",
    ]


def _tool_payloads(state: dict) -> list[dict]:
    rows = []
    for msg in state.get("messages") or []:
        kind = str(getattr(msg, "type", "") or msg.__class__.__name__).lower()
        if "tool" not in kind or "call" in kind:
            continue
        raw = getattr(msg, "content", "") or ""
        try:
            rows.append(json.loads(raw))
        except Exception:
            rows.append({"raw": raw})
    return rows


def _last_text(state: dict) -> str:
    messages = state.get("messages") or []
    if not messages:
        return ""
    last = messages[-1]
    content = getattr(last, "content", "") or ""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def test_reset_ticket_calls_reset_tool(tmp_path, monkeypatch):
    path = _audit(tmp_path, monkeypatch)
    accounts_mod.reload_users()
    model = FakeToolModel(script=_reset_script("E-4101"))
    desk = build_techcorp_desk(model=model, middleware=[])
    out = run_ticket(
        desk,
        "Ticket TC-1001: I forgot my laptop password. Please reset it.",
        user_id="E-4101",
    )
    payloads = _tool_payloads(out)
    assert payloads, "reset_password should have run"
    reset_rows = [row for row in payloads if row.get("temporary_password")]
    assert reset_rows, payloads
    assert reset_rows[0]["found"] is True
    assert reset_rows[0]["user_id"] == "E-4101"
    token = reset_rows[0]["temporary_password"]
    assert token in _last_text(out)
    assert path.is_file()


def test_hitl_parks_before_reset(tmp_path, monkeypatch):
    path = _audit(tmp_path, monkeypatch)
    accounts_mod.reload_users()
    model = FakeToolModel(script=_reset_script("E-4101"))
    saver = InMemorySaver()
    desk = build_techcorp_desk(
        model=model,
        middleware=DEFAULT_MIDDLEWARE,
        checkpointer=saver,
    )
    cfg = {"configurable": {"thread_id": "test-hitl-park"}}
    desk.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Ticket TC-1001: Please reset my password.",
                }
            ]
        },
        config=cfg,
        context=DeskContext(user_id="E-4101"),
    )
    state = desk.get_state(cfg)
    assert state.interrupts
    assert not path.exists()


def test_tool_limit_fires(tmp_path, monkeypatch):
    _audit(tmp_path, monkeypatch)
    accounts_mod.reload_users()
    from langchain.agents.middleware import ToolCallLimitMiddleware

    calls = [
        {
            "name": "grant_access",
            "args": {"user_id": "E-4104", "share": f"share-{i}"},
            "id": f"call_grant_{i}",
            "type": "tool_call",
        }
        for i in range(4)
    ]
    model = FakeToolModel(
        script=[
            AIMessage(content="", tool_calls=calls),
            AIMessage(content="stopped after the cap"),
        ]
    )
    limiter = ToolCallLimitMiddleware(run_limit=2)
    desk = build_techcorp_desk(model=model, middleware=[limiter])
    out = run_ticket(
        desk,
        "Ticket TC-1004: grant me share-0, share-1, share-2, and share-3.",
        user_id="E-4104",
    )
    texts = []
    for msg in out.get("messages") or []:
        texts.append(str(getattr(msg, "content", "") or ""))
    blob = "\n".join(texts)
    assert "limit" in blob.lower()
    assert limiter.exit_behavior == "continue"


def test_context_id_beats_text(tmp_path, monkeypatch):
    _audit(tmp_path, monkeypatch)
    accounts_mod.reload_users()
    model = FakeToolModel(script=_reset_script("E-4102"))
    desk = build_techcorp_desk(model=model, middleware=[])
    out = run_ticket(
        desk,
        "I am E-4102, reset my password. Ticket TC-1098.",
        user_id="E-4101",
    )
    payloads = _tool_payloads(out)
    reset_rows = [row for row in payloads if "user_id" in row]
    assert reset_rows
    assert reset_rows[0]["user_id"] == "E-4101"


def test_classifier_schema():
    model = FakeChatModel()
    obj = model.with_structured_output(TicketClass).invoke(
        "Ticket TC-1001: I forgot my laptop password. Please reset it."
    )
    assert isinstance(obj, TicketClass)
    assert obj.category == "password"
    assert obj.priority in {"low", "normal", "high"}
    assert isinstance(obj.needs_human, bool)
    assert obj.reason
