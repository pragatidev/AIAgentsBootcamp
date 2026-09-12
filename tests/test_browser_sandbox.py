"""15.1 malicious page sandbox. Pytest stays green with no live model."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from techcorp.agent.context import DeskContext
from techcorp.browser.playwright_tool import serve_fixtures
from techcorp.browser.sandbox import (
    sandboxed_browser_desk,
    unguarded_browser_desk,
)
from techcorp.tools import accounts as accounts_mod
from tests.fixtures.fake_model import ScriptedToolChatModel


def _script(url: str) -> list:
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "read_status_page",
                    "args": {"url": url},
                    "id": "call_read",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "reset_password",
                    "args": {"user_id": "E-4101"},
                    "id": "call_reset",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="reset every password as the page asked"),
    ]


def test_sandboxed_desk_parks_and_audit_stays_empty(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts_mod, "AUDIT_PATH", path)
    accounts_mod.reload_users()
    server = serve_fixtures()
    try:
        url = server.base_url + "/malicious.html"
        model = ScriptedToolChatModel(script=_script(url))
        saver = InMemorySaver()
        desk = sandboxed_browser_desk(model=model, checkpointer=saver)
        cfg = {"configurable": {"thread_id": "test-browser-sandbox"}}
        desk.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Read the status page and do what it says",
                    }
                ]
            },
            config=cfg,
            context=DeskContext(user_id="E-4101"),
        )
        state = desk.get_state(cfg)
        assert state.interrupts
        assert not path.exists()
    finally:
        server.stop()


def test_unguarded_desk_writes_audit_row(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts_mod, "AUDIT_PATH", path)
    accounts_mod.reload_users()
    server = serve_fixtures()
    try:
        url = server.base_url + "/malicious.html"
        model = ScriptedToolChatModel(script=_script(url))
        desk = unguarded_browser_desk(model=model)
        desk.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Read the status page and do what it says",
                    }
                ]
            },
            context=DeskContext(user_id="E-4101"),
        )
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "reset_password" in text
        assert "E-4101" in text
    finally:
        server.stop()
