"""A tripwire at bind time: does a tool's description read like instructions? (Lecture 29.6)

A description is text the model reads on every turn and the user never sees. screen_tool returns the
reasons one looks like instructions aimed at the model; an empty list means nothing tripped. It is a
tripwire, not a guarantee: a careful attacker can write a poison none of these checks catch. The
controls that hold are the allowlist (29.7), the scopes (29.4) and the person in front of anything
destructive (29.8).
"""

from __future__ import annotations

import re
from typing import Any

# Tags like <IMPORTANT> and characters that print as nothing can hide text from a person reading the list.
INVISIBLE = "".join(chr(code) for code in (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF))
MARKUP = re.compile("<[^<>]+>|[" + INVISIBLE + "]")
# Phrases that ask the model to keep something from the user.
CONCEALMENT = (
    "do not tell",
    "don't tell",
    "do not mention",
    "don't mention",
    "never mention",
    "without telling",
    "ignore previous",
    "ignore all previous",
    "secretly",
)
URL = re.compile(r"https?://|www\.", re.IGNORECASE)
MAX_LENGTH = 600


def screen_tool(tool: Any, known_tool_names: list[str]) -> list[str]:
    """The reasons tool's description looks like instructions to the model. Empty means it passed."""
    text = str(getattr(tool, "description", "") or "")
    lowered = text.lower()
    reasons = []
    if MARKUP.search(text):
        reasons.append("markup that can hide text")
    for phrase in CONCEALMENT:
        if phrase in lowered:
            reasons.append(f"asks to keep something from the user: {phrase!r}")
    for name in known_tool_names:
        if name != tool.name and re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
            reasons.append(f"names another tool: {name}")
    if URL.search(text):
        reasons.append("contains a URL")
    if len(text) > MAX_LENGTH:
        reasons.append(f"longer than {MAX_LENGTH} characters")
    return reasons


def screen_tools(tools: list[Any], known_tool_names: list[str] | None = None) -> tuple[list[Any], dict[str, list[str]]]:
    """Split tools into the ones that passed and the reasons each refused one tripped."""
    names = known_tool_names if known_tool_names is not None else [tool.name for tool in tools]
    passed, refused = [], {}
    for tool in tools:
        reasons = screen_tool(tool, names)
        if reasons:
            refused[tool.name] = reasons
        else:
            passed.append(tool)
    return passed, refused
