"""The agent loop: a model, tools, and a stop.

This file is a fixture. It does not call a live model. Labs replace
`decide_tool` with a real model when that lecture ships. Pytest stays green.
"""

from __future__ import annotations

from typing import Any, Callable

STOP = "stop"


def decide_tool(ticket: str) -> str:
    """Stand-in for the model. Looks at the ticket text. No API."""
    text = ticket.lower()
    if "return" in text or "refund" in text:
        return "orders"
    if "policy" in text:
        return "policy"
    if "human" in text or "escalate" in text:
        return "escalate"
    return STOP


def run_loop(
    ticket: str,
    tools: dict[str, Callable[..., Any]],
    max_steps: int = 4,
) -> dict[str, Any]:
    """Run until stop or the cap. Every step is recorded."""
    steps: list[dict[str, Any]] = []
    used: set[str] = set()
    for _ in range(max_steps):
        action = decide_tool(ticket)
        if action in used:
            action = STOP
        if action == STOP or action not in tools:
            steps.append({"action": STOP, "result": None})
            break
        used.add(action)
        result = tools[action](ticket)
        steps.append({"action": action, "result": result})
        if isinstance(result, dict) and result.get("escalate"):
            steps.append({"action": STOP, "result": None})
            break
    return {"ticket": ticket, "steps": steps}
