"""Helpers for Section 2 labs. Tests import these. Labs keep a copy in view."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel


class TicketClass(BaseModel):
    category: Literal["password", "vpn", "software", "access"]
    priority: Literal["low", "medium", "high"]
    user_id: str
    summary: str


class ImpossibleTicket(BaseModel):
    category: Literal["password", "vpn", "software", "access"]
    planet: Literal["must_be_pluto_office_wing"]


def parse_ticket(raw: str, schema: type[BaseModel] = TicketClass) -> BaseModel:
    """Parse a model reply into a Pydantic object. Strips fences if present."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return schema.model_validate_json(text)


def parse_tool_call_entry(entry: Any) -> dict:
    """Parse one raw tool_calls item into name, id, and JSON arguments."""
    if hasattr(entry, "model_dump"):
        data = entry.model_dump()
    elif isinstance(entry, str):
        data = json.loads(entry)
    else:
        data = dict(entry)
    fn = data.get("function") or {}
    name = fn.get("name") or data.get("name")
    raw_args = fn.get("arguments", data.get("arguments", "{}"))
    if isinstance(raw_args, str):
        args_json = raw_args
        args = json.loads(raw_args) if raw_args else {}
    else:
        args = raw_args or {}
        args_json = json.dumps(args)
    return {
        "id": data.get("id"),
        "name": name,
        "arguments_json": args_json,
        "arguments": args,
        "type": data.get("type") or "function",
    }


def run_desk(model: Any, prompt: str) -> dict:
    """Same agent code for every model. Returns a fixed set of keys."""
    reply = model.invoke(prompt)
    content = getattr(reply, "content", "")
    usage = getattr(reply, "usage_metadata", None)
    model_id = getattr(model, "model", None) or getattr(model, "model_name", None)
    return {
        "model": model_id,
        "content": content,
        "usage": usage,
        "keys": ["model", "content", "usage"],
    }
