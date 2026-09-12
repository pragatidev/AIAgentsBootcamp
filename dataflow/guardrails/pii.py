"""PII and secrets in a DataFlow agent run."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, PIIMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from config import get_chat_model
from dataflow.tools.orders import lookup_order
from dataflow.tools.retrieve import retrieve

SECRET_RE = re.compile(r"sk-\w{20,}")
PII_TOOLS = [lookup_order, retrieve]
_LAST_MESSAGES: list[Any] = []


def redact_secrets(text: str) -> str:
    return SECRET_RE.sub("[REDACTED_SECRET]", text)


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, BaseMessage):
        update: dict[str, Any] = {}
        content = value.content
        if isinstance(content, str) and SECRET_RE.search(content):
            update["content"] = redact_secrets(content)
        elif isinstance(content, list):
            update["content"] = _redact_value(content)
        if isinstance(value, AIMessage) and value.tool_calls:
            new_calls = []
            changed = False
            for call in value.tool_calls:
                if isinstance(call, dict) and "args" in call:
                    args = _redact_value(call["args"])
                    if args != call["args"]:
                        new_calls.append({**call, "args": args})
                        changed = True
                        continue
                new_calls.append(call)
            if changed:
                update["tool_calls"] = new_calls
        if update:
            return value.model_copy(update=update)
        return value
    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


class SecretFilterMiddleware(AgentMiddleware):
    """Redact sk- followed by 20 or more word characters on input, output and tool args."""

    def before_model(self, state, runtime):
        messages = list(state.get("messages") or [])
        if not messages:
            return None
        new_messages = [_redact_value(m) for m in messages]
        return {"messages": new_messages}

    def after_model(self, state, runtime):
        messages = list(state.get("messages") or [])
        if not messages:
            return None
        return {"messages": [_redact_value(m) for m in messages]}

    def wrap_model_call(self, request, handler):
        messages = [_redact_value(m) for m in list(request.messages or [])]
        request = request.override(messages=messages)
        response = handler(request)
        return response

    def wrap_tool_call(self, request, handler):
        call = request.tool_call if hasattr(request, "tool_call") else None
        if isinstance(call, dict) and "args" in call:
            redacted = dict(call)
            redacted["args"] = _redact_value(call.get("args"))
            try:
                request = request.override(tool_call=redacted)
            except Exception:
                pass
        return handler(request)


def build_pii_desk(
    *,
    model: Any = None,
    secret_filter: bool = False,
):
    chat = model if model is not None else get_chat_model()
    middleware = [
        PIIMiddleware("email", strategy="redact"),
        PIIMiddleware("credit_card", strategy="mask"),
    ]
    if secret_filter:
        middleware.append(SecretFilterMiddleware())
    return create_agent(
        model=chat,
        tools=list(PII_TOOLS),
        middleware=middleware,
    )


def export_trace(path: str | Path, messages: list[Any] | None = None) -> Path:
    """Write the run's messages to a jsonl file."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows = messages if messages is not None else list(_LAST_MESSAGES)
    with dest.open("w", encoding="utf-8") as handle:
        for msg in rows:
            if isinstance(msg, dict):
                payload = dict(msg)
            else:
                payload = {
                    "type": str(getattr(msg, "type", None) or msg.__class__.__name__),
                    "content": getattr(msg, "content", None),
                    "name": getattr(msg, "name", None),
                    "tool_calls": getattr(msg, "tool_calls", None),
                }
            handle.write(json.dumps(payload, ensure_ascii=True, default=str) + "\n")
    return dest


def run_pii_ticket(ticket: str, *, model: Any = None, secret_filter: bool = False) -> dict[str, Any]:
    global _LAST_MESSAGES
    desk = build_pii_desk(model=model, secret_filter=secret_filter)
    state = desk.invoke({"messages": [HumanMessage(content=ticket)]})
    messages = list(state.get("messages") or [])
    _LAST_MESSAGES = messages
    return {"messages": messages, "state": state}
