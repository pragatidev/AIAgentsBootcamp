"""The loop create_agent hides, run by hand: answer every tool call the model proposed, then check the pairing."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from pydantic import ValidationError

from techcorp.tools.accounts import grant_access, lookup_user, reset_password

TOOLS_BY_NAME = {t.name: t for t in (lookup_user, reset_password, grant_access)}


def answer_calls(ai: AIMessage, runtime: Any) -> list[ToolMessage]:
    """One ToolMessage for every call the model proposed, each carrying that call's own id.

    reset_password takes the request envelope (runtime); the other tools take their arguments.
    A tool name the desk does not have is a typed miss, never a KeyError.
    """
    answers = []
    for call in ai.tool_calls:
        name = call["name"]
        args = call.get("args") or {}
        if name == "reset_password":
            result = reset_password.func(str(args.get("user_id") or ""), runtime=runtime)
        elif name in TOOLS_BY_NAME:
            try:
                result = TOOLS_BY_NAME[name].invoke(args)
            except ValidationError:
                result = {"found": False, "reason": f"bad arguments for {name}"}
        else:
            result = {"found": False, "reason": f"unknown tool {name}"}
        answers.append(ToolMessage(content=json.dumps(result), tool_call_id=call["id"], name=name))
    return answers


def check_pairing(messages: list) -> list[str]:
    """One problem per tool call that no ToolMessage answers, and one per ToolMessage that answers no call."""
    asked: list[str] = []
    answered: list[str] = []
    for message in messages:
        if isinstance(message, AIMessage):
            asked += [call["id"] for call in message.tool_calls]
        elif isinstance(message, ToolMessage):
            answered.append(message.tool_call_id)
    problems = [f"unanswered call {call_id}" for call_id in asked if call_id not in answered]
    problems += [f"stray result {call_id}" for call_id in answered if call_id not in asked]
    return problems
