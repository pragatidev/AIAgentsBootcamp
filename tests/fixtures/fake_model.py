"""Fixture chat model for pytest. Returns a fixed route. Not a keyword stand-in in the graph."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk


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


def _split_reply(text: str) -> tuple[str, str]:
    body = text or "ok"
    mid = max(1, len(body) // 2)
    return body[:mid], body[mid:]


def _schema_name(schema: Any) -> str:
    return str(getattr(schema, "__name__", "") or "")


def _schema_fields(schema: Any) -> set[str]:
    fields = getattr(schema, "model_fields", None) or {}
    return set(fields)


def _is_resume_score_schema(schema: Any) -> bool:
    name = _schema_name(schema)
    if name == "ResumeScore":
        return True
    fields = _schema_fields(schema)
    return "score" in fields and "fit" in fields and "reason" in fields


def _is_billing_finding_schema(schema: Any) -> bool:
    name = _schema_name(schema)
    if name == "BillingFinding":
        return True
    fields = _schema_fields(schema)
    return "duplicate_charge" in fields and "missing_tax_line" in fields


class FakeChatModel:
    """Duck-typed chat model. with_structured_output returns the fixed route
    or a payload from `structured` keyed by schema name."""

    def __init__(
        self,
        route: str = "orders",
        reply: str = "looked up desk lamp",
        structured: dict[str, Any] | None = None,
    ) -> None:
        self.route = route
        self.reply = reply
        self.structured = dict(structured or {})
        self.calls = 0
        self.invoke_calls = 0
        self.stream_calls = 0

    def invoke(self, messages: Any, **kwargs: Any) -> AIMessage:
        self.calls += 1
        self.invoke_calls += 1
        return AIMessage(content=self.reply)

    def stream(self, messages: Any, **kwargs: Any):
        """Yield the reply in two chunks so messages mode has tokens."""
        self.calls += 1
        self.stream_calls += 1
        first, second = _split_reply(self.reply)
        yield AIMessageChunk(content=first)
        yield AIMessageChunk(content=second)

    def _stream(self, messages: Any, stop: Any = None, **kwargs: Any):
        first, second = _split_reply(self.reply)
        yield ChatGenerationChunk(message=AIMessageChunk(content=first))
        yield ChatGenerationChunk(message=AIMessageChunk(content=second))

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        route = self.route
        structured = self.structured
        name = _schema_name(schema)

        class _Runner:
            def invoke(self, messages: Any, **kw: Any) -> Any:
                if name in structured:
                    payload: dict[str, Any] = dict(structured[name])
                elif _is_preference_schema(schema):
                    text = _last_user_text(messages).lower()
                    if "email" in text:
                        payload = {
                            "channel": "email",
                            "stated": True,
                        }
                    else:
                        payload = {"channel": "none", "stated": False}
                elif _is_resume_score_schema(schema):
                    payload = dict(
                        structured.get("ResumeScore")
                        or {
                            "score": 80,
                            "fit": "strong",
                            "reason": "fixture score",
                        }
                    )
                elif _is_billing_finding_schema(schema):
                    payload = dict(
                        structured.get("BillingFinding")
                        or {
                            "duplicate_charge": False,
                            "missing_tax_line": False,
                            "disputed_fee": False,
                        }
                    )
                else:
                    payload = {"route": route}
                if hasattr(schema, "model_validate"):
                    return schema.model_validate(payload)
                try:
                    return schema(**payload)
                except Exception:
                    return payload

        return _Runner()


class FakeToolModel:
    """Duck-typed chat model. Yields one tool call, then a final AI message."""

    def __init__(self, script: list[Any] | None = None) -> None:
        self._script = script
        self._i = 0
        self._tools: Any = None

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeToolModel:
        self._tools = tools
        return self

    def invoke(self, messages: Any, **kwargs: Any) -> AIMessage:
        if self._script is not None:
            item = self._script[min(self._i, len(self._script) - 1)]
            self._i += 1
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
