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


def test_fixture_classifier_fills_a_ticketclass():
    # The fixture router, not the schema: the list of categories is pinned in tests/test_lab_05_10.py.
    model = FakeChatModel()
    obj = model.with_structured_output(TicketClass).invoke(
        "Ticket TC-1001: I forgot my laptop password. Please reset it."
    )
    assert isinstance(obj, TicketClass)
    assert obj.category == "password"
    assert obj.priority in {"low", "normal", "high"}
    assert isinstance(obj.needs_human, bool)
    assert obj.reason


def test_desk_context_new_fields_have_defaults():
    ctx = DeskContext(user_id="E-4101")
    assert (ctx.user_id, ctx.region, ctx.role) == ("E-4101", "US", "employee")
    assert ctx.approver is None and ctx.ticket_id is None and ctx.request_id is None


def test_reset_run_prints_no_serializer_warning(tmp_path, monkeypatch):
    # The runtime parameter is ToolRuntime[Any]; a bare ToolRuntime made pydantic warn about the
    # context field on every reset ("PydanticSerializationUnexpectedValue ... field_name='context'").
    import warnings

    _audit(tmp_path, monkeypatch)
    accounts_mod.reload_users()
    desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script("E-4101")), middleware=[])
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        out = run_ticket(desk, "Ticket TC-1001: please reset my password.", user_id="E-4101")
    assert any(row.get("found") for row in _tool_payloads(out))


def _grant_script(user_id: str = "E-4104", share: str = "finance-q3") -> list:
    call = {"name": "grant_access", "args": {"user_id": user_id, "share": share}, "id": "call_grant", "type": "tool_call"}
    return [AIMessage(content="", tool_calls=[call]), "echo_tool"]


def test_hitl_parks_before_grant(tmp_path, monkeypatch):
    path = _audit(tmp_path, monkeypatch)
    accounts_mod.reload_users()
    desk = build_techcorp_desk(
        model=FakeToolModel(script=_grant_script()),
        middleware=DEFAULT_MIDDLEWARE,
        checkpointer=InMemorySaver(),
    )
    out = run_ticket(desk, "Ticket TC-1004: grant me finance-q3.", user_id="E-4104")
    assert out["__interrupt__"]
    assert out["__interrupt__"][0].value["action_requests"][0]["name"] == "grant_access"
    assert not path.exists()


def test_gate_names_are_real_tools():
    from techcorp.agent.desk import DEFAULT_TOOLS, WRITE_TOOLS, write_gate

    tool_names = {t.name for t in DEFAULT_TOOLS}
    gated = set(write_gate().interrupt_on)
    assert gated <= tool_names, gated - tool_names
    assert gated == set(WRITE_TOOLS) == {"reset_password", "grant_access"}


def test_gate_keeps_four_choices():
    from techcorp.agent.desk import write_gate

    for config in write_gate().interrupt_on.values():
        assert config["allowed_decisions"] == ["approve", "edit", "reject", "respond"]


def test_gate_description_names_the_acting_id(tmp_path, monkeypatch):
    _audit(tmp_path, monkeypatch)
    desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script("E-4102")))
    out = run_ticket(desk, "I am E-4102, reset my password.", user_id="E-4101")
    description = out["__interrupt__"][0].value["action_requests"][0]["description"]
    assert description.startswith("reset_password will act on E-4101.")
    assert "E-4102" in description


def test_default_build_gates_reset(tmp_path, monkeypatch):
    path = _audit(tmp_path, monkeypatch)
    desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script("E-4101")))
    out = run_ticket(desk, "Ticket TC-1001: please reset my password.", user_id="E-4101")
    assert out["__interrupt__"]
    assert not path.exists()


def test_explicit_empty_middleware_stays_ungated(tmp_path, monkeypatch):
    path = _audit(tmp_path, monkeypatch)
    desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script("E-4101")), middleware=[])
    out = run_ticket(desk, "Ticket TC-1001: please reset my password.", user_id="E-4101")
    assert "__interrupt__" not in out
    assert path.is_file()


def test_approve_runs_reset_once_and_audits(tmp_path, monkeypatch):
    from langgraph.types import Command

    path = _audit(tmp_path, monkeypatch)
    desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script("E-4101")))
    run_ticket(desk, "Ticket TC-1001: please reset my password.", user_id="E-4101", thread_id="t-approve")
    out = desk.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config={"configurable": {"thread_id": "t-approve"}},
        context=DeskContext(user_id="E-4101"),
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["action"] == "reset_password" and row["user_id"] == "E-4101"
    assert "temporary_password" not in row
    token = [p for p in _tool_payloads(out) if p.get("found")][0]["temporary_password"]
    assert token in _last_text(out)


def test_reply_text_joins_text_blocks():
    from techcorp.agent.desk import reply_text

    blocks = [{"type": "reasoning", "reasoning": "thinking"}, {"type": "text", "text": "Done. "}, {"type": "text", "text": "TC-1001"}]
    assert reply_text({"messages": [AIMessage(content=blocks)]}) == "Done. TC-1001"
    assert reply_text({"messages": [AIMessage(content="plain")]}) == "plain"
    assert reply_text({"messages": []}) == ""


def test_run_ticket_puts_request_and_ticket_ids_on_the_audit_line(tmp_path, monkeypatch):
    path = _audit(tmp_path, monkeypatch)
    desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script("E-4101")), middleware=[])
    run_ticket(desk, "Ticket TC-1001: reset it.", user_id="E-4101", ticket_id="TC-1001", request_id="req-1")
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["ticket_id"] == "TC-1001" and row["request_id"] == "req-1"


def test_answer_ticket_reports_a_parked_write(tmp_path, monkeypatch):
    from techcorp.agent.desk import answer_ticket

    path = _audit(tmp_path, monkeypatch)
    reply = answer_ticket("Ticket TC-1001: reset it.", "E-4101", model=FakeToolModel(script=_reset_script("E-4101")))
    assert reply.startswith("Waiting for a person to approve: reset_password will act on E-4101.")
    assert not path.exists()


def test_answer_ticket_returns_the_reply():
    from techcorp.agent.desk import answer_ticket

    model = FakeToolModel(script=[AIMessage(content="I cannot help with that from the IT desk: no. Please contact Network Support. TC-1002")])
    assert answer_ticket("Ticket TC-1002: VPN drops.", "E-4102", model=model).endswith("TC-1002")


def test_handle_ticket_parks_then_approves(tmp_path, monkeypatch):
    from techcorp.agent.desk import handle_ticket

    path = _audit(tmp_path, monkeypatch)
    desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script("E-4101")))
    parked = handle_ticket(desk, "Ticket TC-1001: reset it.", user_id="E-4101", thread_id="h-1")
    assert parked["parked"] is True and parked["action_requests"][0]["name"] == "reset_password"
    assert not path.exists()
    desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script("E-4101")))
    done = handle_ticket(
        desk, "Ticket TC-1001: reset it.", user_id="E-4101", thread_id="h-2",
        decision={"decisions": [{"type": "approve"}]},
    )
    assert done["parked"] is True
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert '"temporary_password"' in done["reply"]


def test_reject_decision_writes_no_audit(tmp_path, monkeypatch):
    from techcorp.agent.desk import handle_ticket

    path = _audit(tmp_path, monkeypatch)
    desk = build_techcorp_desk(model=FakeToolModel(script=_reset_script("E-4101")))
    out = handle_ticket(
        desk, "Ticket TC-1001: reset it.", user_id="E-4101", thread_id="h-3",
        decision={"decisions": [{"type": "reject", "message": "not today"}]},
    )
    assert out["parked"] is True
    assert "not today" in out["reply"]
    assert not path.exists()


def test_tool_limit_per_tool_name(tmp_path, monkeypatch):
    from langchain.agents.middleware import ToolCallLimitMiddleware

    _audit(tmp_path, monkeypatch)
    calls = [
        {"name": "lookup_user", "args": {"query": f"E-410{i}"}, "id": f"l{i}", "type": "tool_call"}
        for i in (1, 2, 3)
    ]
    model = FakeToolModel(script=[AIMessage(content="", tool_calls=calls), AIMessage(content="two of three")])
    desk = build_techcorp_desk(model=model, tools=[accounts_mod.lookup_user], middleware=[ToolCallLimitMiddleware(tool_name="lookup_user", run_limit=2)])
    out = run_ticket(desk, "Ticket TC-1102: look up three people.", user_id="E-4101")
    refused = [m for m in out["messages"] if m.type == "tool" and m.status == "error"]
    assert len(refused) == 1
    assert "Do not call 'lookup_user' again." in refused[0].content


def test_scope_band_says_what_the_tools_can_do():
    # Ruling LC-2.3 (a): VPN answers come from the record or a tool; faults and installs go to a person.
    from techcorp.agent.prompts import DESK_SYSTEM_PROMPT
    from techcorp.browser.playwright_tool import BROWSER_SYSTEM

    scope = [line for line in DESK_SYSTEM_PROMPT.splitlines() if line.startswith("Scope:")][0]
    assert "vpn_enabled" in scope and "VPN questions you can answer" in scope
    assert "you do not install software" in scope
    assert "software install questions" not in scope
    # Section 39's browser desk is built on this prompt and keeps VPN in scope through its status tool.
    assert scope in BROWSER_SYSTEM and "or from a tool you have" in scope
