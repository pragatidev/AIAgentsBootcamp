"""Fixture chat model for pytest. Returns a fixed route. Not a keyword stand-in in the graph."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage


def _messages_text(messages: Any) -> str:
    if isinstance(messages, str):
        return messages
    if isinstance(messages, list):
        parts: list[str] = []
        for item in messages:
            if isinstance(item, dict):
                parts.append(str(item.get("content", "")))
            else:
                parts.append(str(getattr(item, "content", item)))
        return "\n".join(parts)
    return str(messages)


def _last_user_text(messages: Any) -> str:
    if isinstance(messages, str):
        return messages
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict):
                role = str(item.get("role") or item.get("type") or "").lower()
                if role in ("user", "human"):
                    return str(item.get("content", ""))
            else:
                role = str(
                    getattr(item, "type", "") or getattr(item, "role", "")
                ).lower()
                if role in ("user", "human"):
                    return str(getattr(item, "content", "") or "")
        return _messages_text(messages)
    return str(messages)


def _is_preference_schema(schema: Any) -> bool:
    name = str(getattr(schema, "__name__", "") or "")
    if name == "PreferenceDecision":
        return True
    fields = getattr(schema, "model_fields", None) or {}
    return "channel" in fields and "stated" in fields


def _is_ticket_schema(schema: Any) -> bool:
    name = str(getattr(schema, "__name__", "") or "")
    if name in {"TicketClass", "TicketClassNoVpn"}:
        return True
    fields = getattr(schema, "model_fields", None) or {}
    return "category" in fields and "priority" in fields and "needs_human" in fields


def _ticket_payload(messages: Any) -> dict[str, Any]:
    text = _last_user_text(messages).lower()
    if "vpn" in text:
        category = "vpn"
    elif "password" in text or "reset" in text:
        category = "password"
    elif "access" in text or "grant" in text or "share" in text:
        category = "access"
    elif "install" in text or "vs code" in text or "slack" in text:
        category = "software"
    else:
        category = "other"
    return {
        "category": category,
        "priority": "normal",
        "needs_human": category in {"vpn", "software"},
        "reason": "classified from ticket text",
    }


class FakeChatModel:
    """Duck-typed chat model. with_structured_output returns the fixed route
    or a PreferenceDecision when that schema is requested."""

    def __init__(
        self,
        route: str = "orders",
        reply: str = "looked up desk lamp",
    ) -> None:
        self.route = route
        self.reply = reply

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeChatModel:
        return self

    def bind(self, **kwargs: Any) -> FakeChatModel:
        return self

    def invoke(self, messages: Any, **kwargs: Any) -> AIMessage:
        return AIMessage(content=self.reply)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        route = self.route

        class _Runner:
            def invoke(self, messages: Any, **kw: Any) -> Any:
                if _is_preference_schema(schema):
                    text = _last_user_text(messages).lower()
                    if "email" in text:
                        payload: dict[str, Any] = {
                            "channel": "email",
                            "stated": True,
                        }
                    else:
                        payload = {"channel": "none", "stated": False}
                elif _is_ticket_schema(schema):
                    payload = _ticket_payload(messages)
                else:
                    payload = {"route": route}
                if hasattr(schema, "model_validate"):
                    return schema.model_validate(payload)
                try:
                    return schema(**payload)
                except Exception:
                    return payload

        return _Runner()


def _last_tool_content(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    for item in reversed(messages):
        if isinstance(item, dict):
            role = str(item.get("type") or item.get("role") or "").lower()
            if role in {"tool", "toolmessage"}:
                return str(item.get("content") or "")
            continue
        kind = str(getattr(item, "type", "") or item.__class__.__name__).lower()
        if "tool" in kind and "call" not in kind:
            return str(getattr(item, "content", "") or "")
    return ""


class FakeToolModel:
    """Duck-typed chat model. Yields one tool call, then a final AI message.

    Works under create_agent: bind_tools returns self, invoke returns an
    AIMessage, and a script item of the string echo_tool copies the last
    tool result into the reply so tests can assert on a temporary password.
    """

    def __init__(self, script: list[Any] | None = None) -> None:
        self._script = script
        self._i = 0
        self._tools: Any = None

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeToolModel:
        self._tools = tools
        return self

    def bind(self, **kwargs: Any) -> FakeToolModel:
        return self

    def invoke(self, messages: Any, **kwargs: Any) -> AIMessage:
        if self._script is not None:
            item = self._script[min(self._i, len(self._script) - 1)]
            self._i += 1
            if item == "echo_tool":
                content = _last_tool_content(messages)
                return AIMessage(content=f"Done. {content}")
            return item
        text = _messages_text(messages)
        match = re.search(r"DF-\d+", text.upper())
        order_id = match.group(0) if match else "DF-1001"
        if self._i == 0:
            self._i += 1
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_order",
                        "args": {"order_id": order_id},
                        "id": "call_lookup",
                        "type": "tool_call",
                    }
                ],
            )
        self._i += 1
        return AIMessage(
            content=f"Order {order_id} is delivered. Item: desk lamp."
        )
