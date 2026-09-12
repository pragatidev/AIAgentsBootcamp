"""Fixture chat model for pytest. Returns a fixed route. Not a keyword stand-in in the graph."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


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
    fields = _schema_fields(schema)
    return "duplicate_charge" in fields and "missing_tax_line" in fields


def _is_team_billing_finding_schema(schema: Any) -> bool:
    name = _schema_name(schema)
    fields = _schema_fields(schema)
    if "order_id" in fields and "refund_eligible" in fields:
        return True
    return name == "BillingFinding" and "duplicate_charge" not in fields


def _is_next_step_schema(schema: Any) -> bool:
    name = _schema_name(schema)
    if name == "NextStep":
        return True
    fields = _schema_fields(schema)
    return "step" in fields and "why" in fields


class ScriptedToolChatModel(BaseChatModel):
    """BaseChatModel that plays a list of AIMessage tool calls for create_agent."""

    script: list[Any]
    i: int = 0
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-tool-chat-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedToolChatModel:
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls = int(self.calls) + 1
        if not self.script:
            message: Any = AIMessage(content="done")
        elif self.i < len(self.script):
            message = self.script[self.i]
            self.i = int(self.i) + 1
        else:
            last = self.script[-1]
            if getattr(last, "tool_calls", None):
                message = AIMessage(content="done")
            else:
                message = last
        if not isinstance(message, AIMessage):
            message = AIMessage(content=str(message))
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ):
        result = self._generate(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )
        message = result.generations[0].message
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content=getattr(message, "content", "") or "",
                tool_calls=list(getattr(message, "tool_calls", None) or []),
            )
        )


class FakeChatModel:
    """Duck-typed chat model. with_structured_output returns the fixed route
    or a payload from `structured` keyed by schema name.

    Scripted-tool-calls mode: FakeChatModel(tool_script=[AIMessage(...), ...])
    returns a ScriptedToolChatModel that create_deep_agent will accept.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        script = kwargs.get("tool_script")
        if script is not None:
            return ScriptedToolChatModel(script=list(script))
        return object.__new__(cls)

    def __init__(
        self,
        route: str = "orders",
        reply: str = "looked up desk lamp",
        structured: dict[str, Any] | None = None,
        usage_metadata: dict[str, Any] | None = None,
        tool_script: list[Any] | None = None,
    ) -> None:
        self.route = route
        self.reply = reply
        self.structured = dict(structured or {})
        self.usage_metadata = usage_metadata
        self.tool_script = tool_script
        self.calls = 0
        self.invoke_calls = 0
        self.stream_calls = 0
        self._schema_i: dict[str, int] = {}
        self._tools: Any = None

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeChatModel:
        self._tools = tools
        return self

    def invoke(self, messages: Any, **kwargs: Any) -> AIMessage:
        self.calls += 1
        self.invoke_calls += 1
        if self.usage_metadata is not None:
            return AIMessage(
                content=self.reply,
                usage_metadata=self.usage_metadata,
            )
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

    def _take_structured(self, name: str) -> dict[str, Any] | None:
        if name not in self.structured:
            return None
        raw = self.structured[name]
        if isinstance(raw, list):
            i = self._schema_i.get(name, 0)
            self._schema_i[name] = i + 1
            item = raw[i] if i < len(raw) else raw[-1]
            return dict(item)
        return dict(raw)

    def _with_usage(self, parsed: Any) -> Any:
        if self.usage_metadata is None:
            return parsed
        try:
            object.__setattr__(parsed, "usage_metadata", self.usage_metadata)
            return parsed
        except Exception:
            pass

        class _Box:
            def __init__(self, inner: Any, usage: dict[str, Any]) -> None:
                object.__setattr__(self, "_inner", inner)
                object.__setattr__(self, "usage_metadata", usage)

            def __getattr__(self, name: str) -> Any:
                return getattr(self._inner, name)

            def __getitem__(self, key: Any) -> Any:
                inner = self._inner
                if isinstance(inner, dict):
                    return inner[key]
                return getattr(inner, key)

        return _Box(parsed, self.usage_metadata)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        parent = self
        name = _schema_name(schema)
        include_raw = bool(kwargs.get("include_raw"))

        class _Runner:
            def invoke(self, messages: Any, **kw: Any) -> Any:
                parent.calls += 1
                parent.invoke_calls += 1
                payload = parent._take_structured(name)
                if payload is None and _is_preference_schema(schema):
                    text = _last_user_text(messages).lower()
                    if "email" in text:
                        payload = {
                            "channel": "email",
                            "stated": True,
                        }
                    else:
                        payload = {"channel": "none", "stated": False}
                elif payload is None and _is_resume_score_schema(schema):
                    payload = {
                        "score": 80,
                        "fit": "strong",
                        "reason": "fixture score",
                    }
                elif payload is None and _is_billing_finding_schema(schema):
                    payload = {
                        "duplicate_charge": False,
                        "missing_tax_line": False,
                        "disputed_fee": False,
                    }
                elif payload is None and _is_team_billing_finding_schema(schema):
                    payload = {
                        "order_id": "DF-1010",
                        "amount": 22.0,
                        "refund_eligible": True,
                        "reason": "fixture billed twice",
                    }
                elif payload is None and _is_next_step_schema(schema):
                    step = parent.route
                    if step not in {"billing", "policy", "writer", "escalate"}:
                        step = "billing"
                    payload = {"step": step, "why": "fixture"}
                elif payload is None:
                    payload = {"route": parent.route}
                if hasattr(schema, "model_validate"):
                    parsed = schema.model_validate(payload)
                else:
                    try:
                        parsed = schema(**payload)
                    except Exception:
                        parsed = payload
                parsed = parent._with_usage(parsed)
                if include_raw:
                    raw = AIMessage(
                        content=str(payload),
                        usage_metadata=parent.usage_metadata,
                    )
                    return {
                        "raw": raw,
                        "parsed": parsed,
                        "parsing_error": None,
                    }
                return parsed

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
