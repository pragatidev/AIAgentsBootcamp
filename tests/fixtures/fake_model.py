"""Fixture chat model for pytest. Returns a fixed route. Not a keyword stand-in in the graph."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage


class FakeChatModel:
    """Duck-typed chat model. with_structured_output returns the fixed route."""

    def __init__(self, route: str = "orders") -> None:
        self.route = route

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        route = self.route

        class _Runner:
            def invoke(self, messages: Any, **kw: Any) -> Any:
                payload = {"route": route}
                if hasattr(schema, "model_validate"):
                    return schema.model_validate(payload)
                try:
                    return schema(**payload)
                except Exception:
                    return payload

        return _Runner()


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
