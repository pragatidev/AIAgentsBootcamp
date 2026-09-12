"""Plain-Python scratch agent. No create_agent. No LangGraph."""

from __future__ import annotations

import json
from typing import Any, Callable

WRITE_TOOLS = {"reset_password"}

USERS = {
    "E-4101": {
        "name": "Asha Patel",
        "role": "analyst",
        "status": "active",
        "vpn": "enabled",
    },
    "E-4102": {
        "name": "Ben Ortiz",
        "role": "engineer",
        "status": "active",
        "vpn": "flapping",
    },
}

SYSTEM = (
    "You are the TechCorp IT desk. "
    "Use tools when you need a record or a write. "
    "When you have the result, answer in one short sentence and stop. "
    "Never invent a user id."
)


def lookup_user(user_id: str) -> str:
    row = USERS.get(user_id)
    if not row:
        return json.dumps({"found": False, "user_id": user_id})
    return json.dumps({"found": True, "user_id": user_id, **row})


def reset_password(user_id: str) -> str:
    if user_id not in USERS:
        return json.dumps({"found": False, "user_id": user_id, "reset": False})
    return json.dumps(
        {
            "found": True,
            "user_id": user_id,
            "reset": True,
            "temp_password": "Tmp-" + user_id[-4:],
        }
    )


def tool_schema(name: str, description: str, user_id: bool = True) -> dict:
    props = {}
    required = []
    if user_id:
        props["user_id"] = {
            "type": "string",
            "description": "Employee id such as E-4101",
        }
        required.append("user_id")
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        },
    }


def _call_tool(fn: Callable, args: dict) -> str:
    args = args or {}
    try:
        out = fn(**args) if args else fn()
    except TypeError:
        if "user_id" in args:
            out = fn(args["user_id"])
        else:
            out = fn()
    return out if isinstance(out, str) else json.dumps(out)


class ScratchAgent:
    """Model, tools, loop, stop. Cap is checked before every model call."""

    def __init__(
        self,
        call_model: Callable[[list], dict],
        tools: dict[str, Callable],
        *,
        cap: int = 8,
        gate_writes: bool = False,
        approve: Any = "yes",
        system: str = SYSTEM,
    ) -> None:
        self.call_model = call_model
        self.tools = tools
        self.cap = cap
        self.gate_writes = gate_writes
        self.approve = approve
        self.system = system
        self.rounds: list[dict] = []

    def run(self, ticket: str) -> dict:
        self.rounds = []
        messages: list[dict] = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": ticket},
        ]
        n = 0
        while True:
            n += 1
            if n > self.cap:
                self.rounds.append({"round": n, "kind": "cap", "cap": self.cap})
                return {
                    "final": "desk could not finish",
                    "stop": "cap",
                    "cap": self.cap,
                    "rounds": list(self.rounds),
                    "messages": messages,
                }
            reply = self.call_model(messages)
            tool_calls = list(reply.get("tool_calls") or [])
            content = reply.get("content") or ""
            if not tool_calls:
                self.rounds.append(
                    {"round": n, "kind": "final", "content": content}
                )
                messages.append({"role": "assistant", "content": content})
                return {
                    "final": content,
                    "stop": "final",
                    "rounds": list(self.rounds),
                    "messages": messages,
                }
            raw = reply.get("raw_tool_calls")
            if not raw:
                raw = []
                for tc in tool_calls:
                    raw.append(
                        {
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {
                                "name": tc.get("name"),
                                "arguments": tc.get("arguments_json")
                                or json.dumps(tc.get("arguments") or {}),
                            },
                        }
                    )
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": raw,
                }
            )
            for tc in tool_calls:
                name = str(tc.get("name") or "")
                args = tc.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args) if args else {}
                if self.gate_writes and name in WRITE_TOOLS:
                    decision = self.approve
                    if callable(decision):
                        decision = decision()
                    decision_text = str(decision).strip().lower()
                    if decision_text != "yes":
                        self.rounds.append(
                            {
                                "round": n,
                                "kind": "gate",
                                "tool": name,
                                "decision": decision_text,
                            }
                        )
                        return {
                            "final": "write refused",
                            "stop": "gate",
                            "rounds": list(self.rounds),
                            "messages": messages,
                        }
                fn = self.tools.get(name)
                if fn is None:
                    result = json.dumps(
                        {"ok": False, "reason": "unknown tool", "name": name}
                    )
                else:
                    result = _call_tool(fn, args)
                self.rounds.append(
                    {
                        "round": n,
                        "kind": "tool",
                        "name": name,
                        "arguments": args,
                        "result": result,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "content": str(result),
                    }
                )


def openai_caller(tools_schema: list[dict], model_id: str | None = None):
    """Bind tools on the raw OpenAI-compatible endpoint. No create_agent."""
    from openai import OpenAI

    import config
    from src.part1 import parse_tool_call_entry

    base = config.OLLAMA_BASE_URL.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    client = OpenAI(base_url=base, api_key="ollama")
    model = model_id or config.CHAT_MODEL

    def call_model(messages: list) -> dict:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools_schema,
            temperature=0,
            extra_body={"think": False},
        )
        msg = resp.choices[0].message
        parsed = []
        raw = []
        if msg.tool_calls:
            for item in msg.tool_calls:
                raw.append(item.model_dump())
                parsed.append(parse_tool_call_entry(item))
        return {
            "content": msg.content or "",
            "tool_calls": parsed,
            "raw_tool_calls": raw,
            "finish_reason": resp.choices[0].finish_reason,
        }

    return call_model
