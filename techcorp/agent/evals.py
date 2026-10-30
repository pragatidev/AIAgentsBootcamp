"""Score a desk run against what a good answer looks like, in code, with no judge model."""

from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import AIMessage

from techcorp.agent.desk import reply_text

CASES_PATH = Path(__file__).resolve().parents[1] / "data" / "prompt_cases.jsonl"

# The refusal band of DESK_SYSTEM_PROMPT: I cannot help with that from the IT desk: <reason>. Please contact <team>.
REFUSAL_SHAPE = re.compile(r"I cannot help with that from the IT desk: .+?\. Please contact [^.]+\.", re.DOTALL)


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    """One dict per line of the case file."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def tool_calls_of(state: dict) -> list[dict]:
    """Every tool call the model proposed in the run, in order, as name and args."""
    calls = []
    for message in state.get("messages") or []:
        if isinstance(message, AIMessage):
            calls += [{"name": c["name"], "args": c.get("args") or {}} for c in message.tool_calls]
    return calls


def _is_subsequence(wanted: list[str], called: list[str]) -> bool:
    remaining = iter(called)
    return all(name in remaining for name in wanted)


def score_case(case: dict, state: dict) -> dict:
    """Pass or fail one run against its case: tool order, forbidden tools, the refusal shape, the ticket id at the end."""
    called = [c["name"] for c in tool_calls_of(state)]
    reply = reply_text(state)
    order_ok = _is_subsequence(list(case.get("must_call") or []), called)
    forbidden = [name for name in case.get("must_not_call") or [] if name in called]
    refusal_ok = bool(REFUSAL_SHAPE.search(reply)) == bool(case.get("refusal"))
    ticket_ok = reply.strip().rstrip(".!) ").endswith(case["ticket_id"])
    return {
        "called": called,
        "order_ok": order_ok,
        "forbidden": forbidden,
        "refusal_ok": refusal_ok,
        "ticket_ok": ticket_ok,
        "pass": order_ok and not forbidden and refusal_ok and ticket_ok,
    }
