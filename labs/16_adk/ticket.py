"""Google ADK agent on the DataFlow refund ticket.

LiteLlm wrapper pointed at Ollama. The plant is a missing job
instruction so the agent loops (capped). The fix pastes the DataFlow
job and it stops with the policy line.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import config

TICKET = (
    "Hi, I want to return order DF-1001. The desk lamp is unused. "
    "Can I get a refund?"
)
ORDERS_PATH = ROOT / "dataflow" / "data" / "orders.json"
POLICY_PATH = ROOT / "dataflow" / "wiki" / "return_policy.md"

DATAFLOW_JOB = (
    "You are the DataFlow support desk. When the user names an order id "
    "like DF-1001, call lookup_order. When they ask about a return or "
    "refund, call read_return_policy. After you have the order row and "
    "the policy, write one short customer reply that names the order and "
    "quotes the unused 30 day rule. Then stop. Do not loop."
)


def lookup_order_by_id(order_id: str) -> dict:
    orders = json.loads(ORDERS_PATH.read_text(encoding="utf-8"))
    raw = (order_id or "").strip()
    match = re.search(r"DF-\d+", raw.upper())
    key = match.group(0) if match else raw.upper()
    if not key:
        return {"found": False, "reason": "no order id in the ticket"}
    row = orders.get(key)
    if not row:
        return {"found": False, "order_id": key, "reason": "unknown order"}
    return {"found": True, "order_id": key, **row}


def policy_line() -> str:
    for line in POLICY_PATH.read_text(encoding="utf-8").splitlines():
        if "unused" in line.lower() and "30" in line:
            return line.strip()
    return "Returns are allowed within 30 days of delivery when the item is unused."


def lookup_order(order_id: str) -> str:
    """Look up a DataFlow order by id like DF-1001. Returns JSON."""
    return json.dumps(lookup_order_by_id(order_id))


def read_return_policy() -> str:
    """Read the DataFlow return policy wiki."""
    return POLICY_PATH.read_text(encoding="utf-8")


def keep_going() -> str:
    """Call this when the job is unknown. Returns continue."""
    return "job unknown; call keep_going again"


def ollama_base() -> str:
    base = config.OLLAMA_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


def _event_text(event) -> str:
    parts = []
    content = getattr(event, "content", None)
    if content is not None:
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if text:
                parts.append(str(text))
    return "\n".join(parts)


async def run_adk(*, instruction: str, max_llm_calls: int, tools: list) -> dict:
    os.environ["OLLAMA_API_BASE"] = ollama_base()
    from google.adk.agents import LlmAgent
    from google.adk.agents.run_config import RunConfig
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    model = LiteLlm(
        model="ollama_chat/" + config.CHAT_MODEL,
        api_base=ollama_base(),
    )
    agent = LlmAgent(
        name="dataflow_desk",
        model=model,
        instruction=instruction,
        tools=list(tools),
    )
    runner = InMemoryRunner(agent=agent, app_name="dataflow")
    session = await runner.session_service.create_session(
        app_name="dataflow",
        user_id="student",
        session_id="adk-df-1001",
    )
    texts: list[str] = []
    event_count = 0
    async for event in runner.run_async(
        user_id="student",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=TICKET)],
        ),
        run_config=RunConfig(max_llm_calls=max_llm_calls),
    ):
        event_count += 1
        chunk = _event_text(event)
        if chunk:
            texts.append(chunk)
    blob = "\n".join(texts)
    empty = not bool(instruction.strip())
    needle = "Returns are allowed within 30 days of delivery when the item is unused."
    return {
        "instruction_empty": empty,
        "max_llm_calls": max_llm_calls,
        "event_count": event_count,
        "reply": blob,
        "order_row": None if empty else lookup_order_by_id("DF-1001"),
        "policy_line": None if empty else policy_line(),
        "has_policy_line": (not empty) and needle.lower() in blob.lower(),
        "hit_cap": event_count >= max_llm_calls,
        "fixture": False,
        "model": config.CHAT_MODEL,
        "base_url": config.OLLAMA_BASE_URL,
    }


def run_fixture(*, instruction: str, max_llm_calls: int, reason: str) -> dict:
    """Honest fixture: no invented model reply. The cap and the job still print."""
    loops = 0
    stopped = False
    if not instruction.strip():
        while loops < max_llm_calls:
            loops += 1
        stopped = False
        reply = ""
    else:
        loops = 1
        stopped = True
        reply = policy_line()
    return {
        "instruction_empty": not bool(instruction.strip()),
        "max_llm_calls": max_llm_calls,
        "event_count": loops,
        "reply": reply,
        "order_row": lookup_order_by_id("DF-1001") if stopped else None,
        "policy_line": policy_line() if stopped else None,
        "has_policy_line": stopped,
        "stopped": stopped,
        "fixture": True,
        "fixture_reason": reason,
        "model": config.CHAT_MODEL,
        "base_url": config.OLLAMA_BASE_URL,
    }


def run(*, instruction: str, max_llm_calls: int) -> dict:
    tools = [keep_going] if not instruction.strip() else [lookup_order, read_return_policy]
    try:
        return asyncio.run(
            run_adk(instruction=instruction, max_llm_calls=max_llm_calls, tools=tools)
        )
    except Exception as exc:
        name = type(exc).__name__
        if "LimitExceeded" in name or "max number of llm" in str(exc).lower():
            empty = not bool(instruction.strip())
            return {
                "instruction_empty": empty,
                "max_llm_calls": max_llm_calls,
                "event_count": max_llm_calls,
                "reply": "",
                "order_row": None if empty else lookup_order_by_id("DF-1001"),
                "policy_line": None if empty else policy_line(),
                "has_policy_line": False,
                "hit_cap": True,
                "fixture": False,
                "cap_error": name + ": " + str(exc)[:300],
                "model": config.CHAT_MODEL,
                "base_url": config.OLLAMA_BASE_URL,
            }
        return run_fixture(
            instruction=instruction,
            max_llm_calls=max_llm_calls,
            reason=name + ": " + str(exc)[:500],
        )


if __name__ == "__main__":
    empty = "--empty-job" in sys.argv
    instruction = "" if empty else DATAFLOW_JOB
    cap = 4 if empty else 8
    print(json.dumps(run(instruction=instruction, max_llm_calls=cap), indent=2, ensure_ascii=True))
