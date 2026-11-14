# %%
"""Lab 17.5: cap a runaway graph and log why it stopped.

What we build: four brakes on a planner loop that never finishes. The planted loop asks the model for the next
step of T-3002 and never sets done, so nothing inside it will ever stop it. You type two of the brakes: the
planner that reads remaining_steps (the steps the run has left, filled in by LangGraph) and finishes on purpose
with an honest reply when two or fewer are left, and an async slow_lookup that takes three seconds, added with
timeout=1, a retry on the timeout, and the package's error handler. The other two are the package's: the
recursion limit, the hard stop on the planted loop, and a spend cap that stops a summarize loop once it has
used its token budget. Each brake logs one line saying why the run stopped.

What you learn: the recursion limit counts supersteps and raises GraphRecursionError when the run passes it.
The library's default is 10,007, printed below, so it will not save your bill: set your own. RemainingSteps lets
a node see the end coming and stop cleanly instead of crashing into the limit. timeout= cancels one slow
attempt, which only works on an async node, and the retry policy can treat the timeout as worth one more try;
the error handler turns the last one into a typed miss. A spend cap is plain state and a conditional edge.

What will be true on your screen: the model line and the versions, default_recursion_limit 10007, then one
stopped_by line per brake: recursion_limit with Recursion limit of 8 reached; remaining_steps with the steps
taken and "The desk could not finish this request within its step budget."; timeout with NodeTimeoutError, the
seconds the two attempts and the wait between them took in all, and the detail line naming the one second timeout and the attempt's elapsed
time; spend_cap with the tokens spent over the budget of 600 and the model calls. With the break, the run stops when build_timeout compiles,
on ValueError: Node timeouts are only supported for async nodes because sync Python execution cannot be safely cancelled in-process.
"""

from importlib.metadata import version
from pathlib import Path
import asyncio
import json
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph._internal._config import DEFAULT_RECURSION_LIMIT
from langgraph.errors import GraphRecursionError, NodeTimeoutError
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.runaway import (
    PLAN_SYSTEM,
    GracefulState,
    TimeoutState,
    build_runaway,
    build_spend_capped,
    timeout_error_handler,
)

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))
print("default_recursion_limit", DEFAULT_RECURSION_LIMIT)

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
TICKET = by_id["T-3002"]["text"]
CONTEXT = DeskContext(model=chat)


def stopped_by(brake: str, detail: str) -> None:
    """The log line each brake writes: which brake stopped the run, and what it said."""
    print("stopped_by", brake, "|", detail)


# %%
# TYPE THIS: planner, slow_lookup and build_timeout. The signatures and docstrings are given; you type the rest.
# The package's finished versions are the planner in build_graceful, slow_lookup and build_timeout_demo in
# dataflow/graphs/runaway.py (lines 178 to 204 and 217 to 254).
def planner(state: GracefulState) -> dict:
    """Plan one more step, or finish on purpose when two or fewer steps are left."""
    remaining = state["remaining_steps"]
    steps = state.get("steps", 0) + 1
    if remaining <= 2:
        reply = "The desk could not finish this request within its step budget."
        return {"done": True, "steps": steps, "reply": reply}
    message = chat.invoke([{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": state["ticket"]}])
    return {"plan": message.content, "steps": steps, "done": False}


async def slow_lookup(state: TimeoutState) -> dict:
    """A carrier lookup that takes three seconds. Async, so a timeout can cancel the wait."""
    await asyncio.sleep(3)
    return {"lookup": {"found": True, "reason": "carrier responded"}}


def build_timeout():
    """slow_lookup with one second per attempt, one retry on the timeout, then the typed miss."""
    builder = StateGraph(TimeoutState)
    builder.add_node(
        "slow_lookup",
        slow_lookup,
        timeout=1,
        retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.1, retry_on=NodeTimeoutError),
        error_handler=timeout_error_handler,
    )
    builder.add_edge(START, "slow_lookup")
    builder.add_edge("slow_lookup", END)
    return builder.compile()


# BREAK: in build_timeout, change the line slow_lookup, (the node handed to add_node) to slow_lookup_sync, (the same
# three seconds written as a plain def, below) and run. The first two brakes run as before; then the run stops when
# build_timeout compiles, on ValueError: Node timeouts are only supported for async nodes because sync Python
# execution cannot be safely cancelled in-process. Node 'slow_lookup' is sync. Put it back and run.
def slow_lookup_sync(state: TimeoutState) -> dict:
    """The same lookup as a plain def: time.sleep cannot be cancelled once it has started."""
    time.sleep(3)
    return {"lookup": {"found": True, "reason": "carrier responded"}}


# %%
# Given: the planner loop your planner runs in. route goes back to the planner until done is set.
def build_planner_loop():
    builder = StateGraph(GracefulState, context_schema=DeskContext)
    builder.add_node("planner", planner)
    builder.add_edge(START, "planner")
    builder.add_conditional_edges("planner", lambda state: END if state.get("done") else "planner")
    return builder.compile()


# %%
# Brake 1, the counter: the planted loop, capped at 8 supersteps.
try:
    build_runaway().invoke({"ticket": TICKET, "done": False}, {"recursion_limit": 8}, context=CONTEXT)
except GraphRecursionError as exc:
    stopped_by("recursion_limit", str(exc).splitlines()[0])

# %%
# Brake 2, the fuel gauge: your planner, with the same limit of 8.
out = build_planner_loop().invoke({"ticket": TICKET}, {"recursion_limit": 8}, context=CONTEXT)
stopped_by("remaining_steps", f"steps {out['steps']} done {out['done']} reply {out['reply']}")

# %%
# Brake 3, the stopwatch: your slow lookup, one second per attempt.
started = time.perf_counter()
out = asyncio.run(build_timeout().ainvoke({"ticket": TICKET}))
seconds = round(time.perf_counter() - started, 1)
stopped_by("timeout", f"{out['timeout_error']} after {seconds} s in all, lookup {out['lookup']}")
print("timeout_detail", out["timeout_detail"])

# %%
# Brake 4, the spend meter: a summarize loop that stops once it has used 600 tokens.
out = build_spend_capped(budget_tokens=600).invoke({"ticket": TICKET}, context=CONTEXT)
stopped_by("spend_cap", f"{out['reply']} counted from {out['usage_source']}")
