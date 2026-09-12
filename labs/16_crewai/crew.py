"""CrewAI crew for the DataFlow refund ticket.

Researcher, policy lookup, writer. The plant lets two agents send the
customer reply. The fix locks the reply to the writer.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

os.environ["CREWAI_TRACING_ENABLED"] = "false"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import config
from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool

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


@tool("lookup_order")
def lookup_order_tool(order_id: str) -> str:
    """Look up a DataFlow order by id like DF-1001. Returns JSON."""
    return json.dumps(lookup_order_by_id(order_id))


@tool("read_return_policy")
def read_return_policy_tool() -> str:
    """Read the DataFlow return policy wiki."""
    return POLICY_PATH.read_text(encoding="utf-8")


def ollama_llm() -> LLM:
    base = config.OLLAMA_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return LLM(
        model="ollama/" + config.CHAT_MODEL,
        base_url=base,
        temperature=0,
    )


def looks_like_reply(text: str) -> bool:
    lower = (text or "").lower()
    if '"found"' in lower and "order_id" in lower:
        return False
    if "policy line" in lower and "dear" not in lower:
        return False
    return "dear" in lower or "best regards" in lower or "customer support" in lower


def build_crew(*, lock_writer: bool) -> Crew:
    llm = ollama_llm()
    researcher = Agent(
        role="Researcher",
        goal="Find the order row for the ticket.",
        backstory="You look up DataFlow orders. You do not invent rows.",
        llm=llm,
        tools=[lookup_order_tool],
        verbose=False,
        allow_delegation=False,
    )
    policy_agent = Agent(
        role="Policy lookup",
        goal="Quote the return policy that applies.",
        backstory="You read the DataFlow return wiki. You quote the unused 30 day rule.",
        llm=llm,
        tools=[read_return_policy_tool],
        verbose=False,
        allow_delegation=False,
    )
    writer = Agent(
        role="Writer",
        goal="Write the one customer reply.",
        backstory="You write the customer facing answer from facts the others found.",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    if lock_writer:
        research_task = Task(
            description=(
                "Ticket:\n" + TICKET + "\n"
                "Call lookup_order for DF-1001. Return the JSON row only. "
                "Do not write to the customer."
            ),
            expected_output="The order JSON for DF-1001.",
            agent=researcher,
        )
        policy_task = Task(
            description=(
                "Read the return policy. Quote the unused 30 day line. "
                "Do not write to the customer."
            ),
            expected_output="The unused 30 day policy line.",
            agent=policy_agent,
            context=[research_task],
        )
        write_task = Task(
            description=(
                "Write the one customer reply using the order row and the policy. "
                "Name DF-1001 and the unused 30 day rule. No other agent replies."
            ),
            expected_output="One customer reply.",
            agent=writer,
            context=[research_task, policy_task],
        )
        tasks = [research_task, policy_task, write_task]
    else:
        research_task = Task(
            description=(
                "Ticket:\n" + TICKET + "\n"
                "Look up DF-1001 and write the customer reply yourself."
            ),
            expected_output="A customer reply about the refund.",
            agent=researcher,
        )
        policy_task = Task(
            description="Read the return policy and quote the unused 30 day line.",
            expected_output="The unused 30 day policy line.",
            agent=policy_agent,
            context=[research_task],
        )
        write_task = Task(
            description=(
                "Ticket:\n" + TICKET + "\n"
                "Write the customer reply using the order and the policy."
            ),
            expected_output="A customer reply about the refund.",
            agent=writer,
            context=[research_task, policy_task],
        )
        tasks = [research_task, policy_task, write_task]
    kwargs = dict(
        agents=[researcher, policy_agent, writer],
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )
    try:
        return Crew(tracing=False, **kwargs)
    except TypeError:
        return Crew(**kwargs)


def run(*, lock_writer: bool) -> dict:
    crew = build_crew(lock_writer=lock_writer)
    result = crew.kickoff()
    outputs = []
    tasks_output = getattr(result, "tasks_output", None) or []
    for item in tasks_output:
        agent_name = str(getattr(getattr(item, "agent", None), "role", "") or "")
        raw = str(getattr(item, "raw", "") or item)
        outputs.append({"agent": agent_name, "raw": raw})
    reply_outputs = [row for row in outputs if looks_like_reply(row["raw"])]
    final = str(getattr(result, "raw", "") or result)
    return {
        "lock_writer": lock_writer,
        "model": config.CHAT_MODEL,
        "base_url": config.OLLAMA_BASE_URL,
        "order_row": lookup_order_by_id("DF-1001"),
        "policy_line": policy_line(),
        "task_outputs": outputs,
        "reply_count": len(reply_outputs),
        "final": final,
    }


if __name__ == "__main__":
    lock = "--lock-writer" in sys.argv
    print(json.dumps(run(lock_writer=lock), indent=2, ensure_ascii=True))
