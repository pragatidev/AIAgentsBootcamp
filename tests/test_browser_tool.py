"""15.1 Playwright status tool. Pytest stays green with no live model."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage

from techcorp.browser.playwright_tool import (
    OUTAGE_LINE,
    build_browser_desk,
    read_status_page,
    serve_fixtures,
)
from techcorp.agent.desk import run_ticket
from tests.fixtures.fake_model import ScriptedToolChatModel

ROOT = Path(__file__).resolve().parents[1]


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


def test_fixture_page_yields_outage_line():
    server = serve_fixtures()
    try:
        url = server.base_url + "/status.html"
        result = read_status_page.invoke({"url": url})
        assert result.get("blocked") is not True
        assert result["outage"] == OUTAGE_LINE
        assert result["url"] == url
    finally:
        server.stop()


def test_file_url_is_blocked():
    url = (ROOT / "README.md").resolve().as_uri()
    result = read_status_page.invoke({"url": url})
    assert result["blocked"] is True
    assert result["reason"] == "url not on the allowlist"
    assert "outage" not in result


def test_desk_calls_read_status_page_once():
    server = serve_fixtures()
    try:
        url = server.base_url + "/status.html"
        model = ScriptedToolChatModel(
            script=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_status_page",
                            "args": {"url": url},
                            "id": "call_status",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="VPN gateway is degraded."),
            ]
        )
        desk = build_browser_desk(model=model)
        out = run_ticket(desk, "Is the VPN down?")
        payloads = _tool_payloads(out)
        assert len(payloads) == 1, payloads
        assert payloads[0].get("outage") == OUTAGE_LINE
        assert payloads[0].get("blocked") is not True
        assert model.calls >= 2
    finally:
        server.stop()
