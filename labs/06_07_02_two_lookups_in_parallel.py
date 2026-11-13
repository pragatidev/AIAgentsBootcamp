# %%
"""Lab 16.2: two lookups in parallel.

What we build: the DataFlow desk v6 on the refund ticket T-3001. classify runs first. Then two edges leave
classify, one to lookup (the order row) and one to policy_search (the return policy), so both run in the same
superstep, and two edges come into draft_reply, which waits for both and writes the reply. You type the
notebook, ParallelState, whose results key gathers the two findings, and build_parallel with its four fan
edges. The nodes themselves are the package's. The last cell is the defer run: a fan whose branches have
different lengths, gathered with defer off and then on.

What you learn: nodes started by the same step run together in one superstep, and their writes are applied
together when the step ends. Two writes to one key in one step need a reducer: Annotated[list, operator.add]
adds the two one-item lists into one list of two. Without it LangGraph refuses with InvalidUpdateError rather
than pick a winner. A gather node runs as soon as any branch reaches it, so a branch that takes an extra hop
arrives late and the gather runs twice; defer=True makes it wait until nothing else is left to run.

What will be true on your screen: the model line and the versions, the ticket, results with two rows (source
lookup with DF-1001 and the desk lamp, source policy with wiki/return_policy.md), the model's two-sentence
reply, then the history oldest first: classify alone, then lookup and policy_search in the same step, then
draft_reply, then the end. Last, summarize_runs 2 with defer off and 1 with defer on. With the break, the run
stops on InvalidUpdateError: At key 'results': Can receive only one value per step.
"""

from importlib.metadata import version
from pathlib import Path
import json
import operator
import sys
from typing import Annotated, TypedDict

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.durable import build_two_length_fan
from dataflow.graphs.v6_parallel import classify, draft_reply, lookup, policy_search

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
TICKET = by_id["T-3001"]["text"]
print("ticket T-3001", TICKET)


# %%
# TYPE THIS: ParallelState and build_parallel. The signatures and docstrings are given; you type the rest.
# The package's finished version is ParallelState and _wire_parallel in dataflow/graphs/v6_parallel.py
# (lines 42 to 46 and 132 to 141).
class ParallelState(TypedDict, total=False):
    """The ticket, the route, the findings both lookups add to, and the reply."""
    ticket: str
    route: str
    results: Annotated[list, operator.add]
    reply: str


def build_parallel():
    """classify, then lookup and policy_search side by side, then draft_reply once both are in."""
    builder = StateGraph(ParallelState, context_schema=DeskContext)
    builder.add_node("classify", classify)
    builder.add_node("lookup", lookup)
    builder.add_node("policy_search", policy_search)
    builder.add_node("draft_reply", draft_reply)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "lookup")
    builder.add_edge("classify", "policy_search")
    builder.add_edge("lookup", "draft_reply")
    builder.add_edge("policy_search", "draft_reply")
    builder.add_edge("draft_reply", END)
    return builder.compile(checkpointer=InMemorySaver())


# BREAK: change the results line of ParallelState to results: list (take the reducer off) and run. It compiles,
# classify runs, and then the run stops on InvalidUpdateError: At key 'results': Can receive only one value per
# step. Use an Annotated key to handle multiple values. lookup and policy_search both wrote results in the same
# step, and a plain key keeps one value. Put it back and run.

# %%
graph = build_parallel()
thread = {"configurable": {"thread_id": "lab-16-2"}}
out = graph.invoke({"ticket": TICKET}, thread, context=DeskContext(model=chat))
for row in out["results"]:
    print("result", row)
print("reply", out["reply"])

# %%
# Walk the notebook's history oldest first: each save point and the nodes due next.
history = list(reversed(list(graph.get_state_history(thread))))
print("history_oldest_first", len(history))
for snap in history:
    print("step", snap.metadata["step"], "next", list(snap.next))

# %%
# Moved from the old cache and defer lab: three items fan out, one takes an extra hop (deep_check), and all
# three meet at summarize. Each run of summarize adds one line to runs.
off = build_two_length_fan(defer=False).invoke({})
print("summarize_runs defer False", len(off["runs"]), "results seen each time", off["runs"])
on = build_two_length_fan(defer=True).invoke({})
print("summarize_runs defer True", len(on["runs"]), "results seen each time", on["runs"])
