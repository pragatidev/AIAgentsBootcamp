"""AutoGen SupportFlow team on the DataFlow refund ticket.

Current autogen_agentchat team API. The plant hits the turn cap with
no answer. The fix stops on the writer's message after lookup.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import config
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core.models import ModelFamily
from autogen_ext.models.ollama import OllamaChatCompletionClient

TICKET = (
    "Hi, I want to return order DF-1001. The desk lamp is unused. "
    "Can I get a refund?"
)
ORDERS_PATH = ROOT / "dataflow" / "data" / "orders.json"
POLICY_PATH = ROOT / "dataflow" / "wiki" / "return_policy.md"


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


def make_client() -> OllamaChatCompletionClient:
    base = config.OLLAMA_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return OllamaChatCompletionClient(
        model=config.CHAT_MODEL,
        host=base,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "family": ModelFamily.UNKNOWN,
            "structured_output": False,
        },
    )


def _messages(result) -> list[dict]:
    rows = []
    for msg in getattr(result, "messages", None) or []:
        rows.append(
            {
                "source": str(getattr(msg, "source", "") or ""),
                "type": type(msg).__name__,
                "content": str(getattr(msg, "content", "") or "")[:800],
            }
        )
    return rows


async def run(*, stop_on_writer: bool) -> dict:
    client = make_client()
    try:
        if stop_on_writer:
            lookup = AssistantAgent(
                "lookup",
                model_client=client,
                tools=[lookup_order],
                reflect_on_tool_use=True,
                system_message=(
                    "You look up DataFlow orders. Call lookup_order for DF-1001. "
                    "Then stop talking."
                ),
            )
            policy = AssistantAgent(
                "policy",
                model_client=client,
                tools=[read_return_policy],
                reflect_on_tool_use=True,
                system_message=(
                    "You quote the return policy. Call read_return_policy. "
                    "Quote the unused 30 day line. Then stop talking."
                ),
            )
            writer = AssistantAgent(
                "writer",
                model_client=client,
                system_message=(
                    "You write the one customer reply. Name DF-1001 and the "
                    "unused 30 day rule. Do not keep chatting."
                ),
            )
            termination = TextMessageTermination(source="writer") | MaxMessageTermination(
                max_messages=12
            )
            team = RoundRobinGroupChat(
                [lookup, policy, writer],
                termination_condition=termination,
            )
        else:
            lookup = AssistantAgent(
                "lookup",
                model_client=client,
                system_message="Keep asking the others what the order id means. Do not answer the customer.",
            )
            policy = AssistantAgent(
                "policy",
                model_client=client,
                system_message="Keep asking what the policy is. Do not answer the customer.",
            )
            writer = AssistantAgent(
                "writer",
                model_client=client,
                system_message="Ask the others for facts. Do not write a final answer yet.",
            )
            team = RoundRobinGroupChat(
                [lookup, policy, writer],
                termination_condition=MaxMessageTermination(max_messages=3),
            )
        result = await team.run(task=TICKET)
        rows = _messages(result)
        blob = "\n".join(row["content"] for row in rows)
        return {
            "stop_on_writer": stop_on_writer,
            "model": config.CHAT_MODEL,
            "base_url": config.OLLAMA_BASE_URL,
            "stop_reason": str(getattr(result, "stop_reason", "") or ""),
            "message_count": len(rows),
            "messages": rows,
            "order_row": lookup_order_by_id("DF-1001") if stop_on_writer else None,
            "policy_line": policy_line() if (stop_on_writer and "30" in blob) else (
                policy_line() if stop_on_writer else None
            ),
            "has_policy_line": "30" in blob and "unused" in blob.lower(),
        }
    finally:
        await client.close()


def run_sync(*, stop_on_writer: bool) -> dict:
    return asyncio.run(run(stop_on_writer=stop_on_writer))


if __name__ == "__main__":
    stop = "--stop-on-writer" in sys.argv
    print(json.dumps(run_sync(stop_on_writer=stop), indent=2, ensure_ascii=True))
