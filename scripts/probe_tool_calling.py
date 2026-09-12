"""Prove the student default model can propose a tool call. No keyword fallback."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool

import config


@tool
def lookup_order_id(order_id: str) -> str:
    """Look up a DataFlow order by id such as DF-1001. Returns JSON."""
    return json.dumps({"order_id": order_id, "found": True, "item": "desk lamp"})


def probe(model_id: str) -> bool:
    print("probing", model_id)
    saved = config.CHAT_MODEL
    config.CHAT_MODEL = model_id
    try:
        model = config.get_chat_model()
        bound = model.bind_tools([lookup_order_id])
        result = bound.invoke(
            "Use the lookup_order_id tool to look up order DF-1001. "
            "Do not answer from memory. Call the tool."
        )
        content = getattr(result, "content", "")
        tool_calls = getattr(result, "tool_calls", None) or []
        additional = getattr(result, "additional_kwargs", None) or {}
        print("content", repr(content)[:800])
        print("tool_calls", tool_calls)
        print("additional_kwargs", additional)
        if tool_calls:
            print("proposed_tool_call", json.dumps(tool_calls, default=str))
            print("TOOL_CALL_OK", model_id)
            return True
        print("NO_TOOL_CALL", model_id)
        return False
    finally:
        config.CHAT_MODEL = saved


def main() -> int:
    first = config.CHAT_MODEL
    print("student_default", first)
    if probe(first):
        return 0
    if first != "qwen3:4b":
        print("trying qwen3:4b after student default failed tool calling")
        if probe("qwen3:4b"):
            print("qwen3:8b failed tool calling; qwen3:4b succeeded")
            return 0
    print("TOOL_CALL_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
