"""OpenAI Agents SDK on the DataFlow refund ticket.

Agent, Runner, and a handoff to a refund agent. The plant writes a
refund with no confirmation. The fix parks behind a human approval hook.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import config
from agents import Agent, Runner, function_tool, set_default_openai_api, set_default_openai_client
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.tracing import set_tracing_disabled
from openai import AsyncOpenAI

from dataflow.tools.orders import lookup_order_by_id
from dataflow.tools.refund import write_refund

TICKET = (
    "Hi, I want to return order DF-1001. The desk lamp is unused. "
    "Can I get a refund?"
)
POLICY_PATH = ROOT / "dataflow" / "wiki" / "return_policy.md"


def policy_line() -> str:
    for line in POLICY_PATH.read_text(encoding="utf-8").splitlines():
        if "unused" in line.lower() and "30" in line:
            return line.strip()
    return "Returns are allowed within 30 days of delivery when the item is unused."


def ollama_base() -> str:
    base = config.OLLAMA_BASE_URL.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    return base


def make_model() -> OpenAIChatCompletionsModel:
    set_tracing_disabled(True)
    set_default_openai_api("chat_completions")
    client = AsyncOpenAI(base_url=ollama_base(), api_key="ollama")
    set_default_openai_client(client, use_for_tracing=False)
    return OpenAIChatCompletionsModel(model=config.CHAT_MODEL, openai_client=client)


@function_tool
def lookup_order(order_id: str) -> str:
    """Look up a DataFlow order by id like DF-1001. Returns JSON."""
    return json.dumps(lookup_order_by_id(order_id))


@function_tool
def read_return_policy() -> str:
    """Read the DataFlow return policy wiki."""
    return POLICY_PATH.read_text(encoding="utf-8")


@function_tool
def issue_refund(order_id: str, amount: float, reason: str) -> str:
    """Issue a pretend refund. Writes one ledger row. No real money."""
    row = write_refund(order_id, amount, reason, actor="openai-agents")
    return json.dumps(row)


@function_tool(needs_approval=True)
def issue_refund_guarded(order_id: str, amount: float, reason: str) -> str:
    """Issue a pretend refund after a human approves. Writes one ledger row."""
    row = write_refund(order_id, amount, reason, actor="openai-agents")
    return json.dumps(row)


def build_desk(*, guarded: bool) -> Agent:
    model = make_model()
    refund_tool = issue_refund_guarded if guarded else issue_refund
    refund_agent = Agent(
        name="Refund agent",
        instructions=(
            "You issue DataFlow refunds. You must call the refund tool now "
            "with order_id DF-1001, amount 49.0, reason unused within 30 days. "
            "Do not ask the customer. Call the tool, then stop."
        ),
        model=model,
        tools=[refund_tool],
    )
    desk = Agent(
        name="DataFlow desk",
        instructions=(
            "You are the DataFlow desk. Call lookup_order for DF-1001 and "
            "read_return_policy. Then hand off to the refund agent. Do not "
            "issue the refund yourself."
        ),
        model=model,
        tools=[lookup_order, read_return_policy],
        handoffs=[refund_agent],
    )
    if guarded:
        return refund_agent
    return desk


def run(*, guarded: bool) -> dict:
    desk = build_desk(guarded=guarded)
    result = Runner.run_sync(desk, TICKET, max_turns=8)
    interruptions = list(getattr(result, "interruptions", None) or [])
    parked = bool(interruptions)
    final = str(getattr(result, "final_output", "") or "")
    return {
        "guarded": guarded,
        "model": config.CHAT_MODEL,
        "base_url": config.OLLAMA_BASE_URL,
        "parked": parked,
        "interruption_count": len(interruptions),
        "final": final,
        "order_row": lookup_order_by_id("DF-1001"),
        "policy_line": policy_line(),
    }


if __name__ == "__main__":
    guarded = "--guard" in sys.argv
    print(json.dumps(run(guarded=guarded), indent=2, ensure_ascii=True))
