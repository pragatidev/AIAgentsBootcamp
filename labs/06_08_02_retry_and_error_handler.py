# %%
"""Lab 17.2: retry policy and error handler on a flaky tool, and a cached node.

What we build: the durable desk, whose first node asks a carrier API where an order is. The carrier is flaky on
purpose: its first two calls time out and the third answers. It also reads the order id first and rejects one
it cannot read, every time. You type the carrier node's add_node, with a retry policy (three tries, a backoff
between them, and only a timeout counts as worth retrying) and an error handler, and the handler itself: when
retries are spent, or the error is not one to retry, it writes a typed miss that says why and sends the run on
to the policy search, so the customer still gets a reply. Four runs: T-3002, the carrier down for good, a ticket
with a typo in its order id, and last, moved from the old cache lab, the cached policy node on three threads.

What you learn: a retry policy is for the world's failures, the ones that may pass if you ask again; LangGraph's
own default list retries a connection error and does not retry a ValueError, because bad input fails the same
way every time. An error handler is the node's fallback: it gets a NodeError holding the real error, and
returns a Command with a typed miss and where to go next, so the graph decides and the run goes on. A cache
policy keeps a node's result for a few seconds, so the same input skips the body; when the time runs out the
body runs again.

What will be true on your screen: the model line and the versions; T-3002: the update from carrier_check with
its log, attempt 1 timeout, attempt 2 timeout, attempt 3 success, the order, the reply; the carrier down: the
update now comes from __error_handler__carrier_check, with three timeouts and the miss "carrier unreachable
after retries"; the typo ticket: the handler again, one attempt, rejected DF-10, and the miss "carrier rejected
the order id"; the default retry list's answer for a ValueError (False) and a
ConnectionError (True); then the cache: policy body runs 1, then still 1 on the second thread, then 2 after
the ttl. With the break, the typo ticket shows three rejected attempts and the wait between them, then the same
miss: every try was spent on an error that could never pass.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph._internal._retry import default_retry_on
from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import CachePolicy, Command, RetryPolicy

import config
import dataflow.graphs.durable as durable
from dataflow.envelope import DeskContext
from dataflow.graphs.durable import DurableState, PolicyInput, carrier_check_checked, policy_search, send_receipt, speak
from dataflow.tools.flaky import CarrierTimeout, reset_flaky, set_always_fail

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
WHERE_IS_IT, RETURN_WINDOW = by_id["T-3002"]["text"], by_id["T-3003"]["text"]
TYPO = "Where is order DF-10O2? Tracking still says in transit."  # written for this lab: a letter O in the id
CONTEXT = DeskContext(model=chat)
CACHE_TTL = 20  # seconds; it must outlast one whole run of the desk on a local model


# %%
# TYPE THIS: carrier_error_handler and add_carrier. The signatures and docstrings are given; you type the rest.
# The package's finished versions are carrier_miss_handler and the carrier_check node of build_durable_checked in
# dataflow/graphs/durable.py (the desk's first version, build_durable, is lines 282 to 325).
def carrier_error_handler(state: DurableState, error: NodeError) -> Command:
    """Retries spent, or an error not worth retrying: write a typed miss that says why, then go on."""
    cause = getattr(error, "error", error)
    if isinstance(cause, ValueError):
        reason = "carrier rejected the order id"
    else:
        reason = "carrier unreachable after retries"
    miss = {"found": False, "reason": reason, "error": type(cause).__name__}
    return Command(goto="policy_search", update={"carrier": miss, "log": list(durable.CARRIER_LOG) or [reason]})


def add_carrier(builder: StateGraph) -> None:
    """The carrier node: three tries with a backoff, a timeout is the only error worth a retry, then the handler."""
    builder.add_node(
        "carrier_check",
        carrier_check_checked,
        retry_policy=RetryPolicy(
            max_attempts=3,
            initial_interval=0.2,
            backoff_factor=2.0,
            retry_on=CarrierTimeout,
        ),
        error_handler=carrier_error_handler,
    )


# BREAK: change retry_on=CarrierTimeout to retry_on=Exception (retry everything) and run. T-3002 and the carrier
# down look the same. Read the typo ticket: attempt 1, 2 and 3 all rejected DF-10, the seconds grow by the backoff
# between them, and the miss is the same as with one try. A ValueError from bad input fails the same way every
# time, which is why LangGraph's default list does not retry it. Put it back and run.

# %%
def build_desk(cache_ttl: int = CACHE_TTL):
    """The durable desk around your carrier: the cached policy search, the receipt, the reply."""
    builder = StateGraph(DurableState, context_schema=DeskContext)
    add_carrier(builder)
    builder.add_node("policy_search", policy_search, input_schema=PolicyInput, cache_policy=CachePolicy(ttl=cache_ttl))
    builder.add_node("send_receipt", send_receipt)
    builder.add_node("speak", speak)
    builder.add_edge(START, "carrier_check")
    builder.add_edge("carrier_check", "policy_search")
    builder.add_edge("policy_search", "send_receipt")
    builder.add_edge("send_receipt", "speak")
    builder.add_edge("speak", END)
    return builder.compile(checkpointer=InMemorySaver(), cache=InMemoryCache())


def run(label: str, ticket: str) -> dict:
    """One ticket on a fresh desk; prints who wrote the carrier's update and its log, then the miss or the order."""
    durable.reset_durable()
    graph = build_desk()
    thread = {"configurable": {"thread_id": f"lab-17-2-{label}"}}
    started = time.perf_counter()
    for update in graph.stream({"ticket": ticket}, thread, context=CONTEXT, stream_mode="updates"):
        for name in ("carrier_check", "__error_handler__carrier_check"):
            if name in update:
                print(label, "update from", name)
                for line in update[name]["log"]:
                    print("  ", label, line)
    seconds = round(time.perf_counter() - started, 2)
    values = graph.get_state(thread).values
    print(label, "carrier", values["carrier"], "seconds", seconds)
    return values


# %%
reset_flaky()
out = run("where_is_it", WHERE_IS_IT)
print("reply", out["reply"])

# %%
reset_flaky()
set_always_fail(True)
out = run("carrier_down", WHERE_IS_IT)
set_always_fail(False)
print("reply", out["reply"])

# %%
reset_flaky()
out = run("typo", TYPO)
print("reply", out["reply"])
print("default_retry_on ValueError", default_retry_on(ValueError("bad id")), "ConnectionError", default_retry_on(ConnectionError("down")))

# %%
# Moved from the old cache and defer lab: the policy search caches its result for CACHE_TTL seconds, keyed on its
# input. POLICY_CALLS counts how often its body really ran.
durable.reset_durable()
reset_flaky()
graph = build_desk()
for label in ("first", "second", "after_ttl"):
    if label == "after_ttl":
        time.sleep(CACHE_TTL + 2)
    reset_flaky()
    graph.invoke({"ticket": RETURN_WINDOW}, {"configurable": {"thread_id": f"lab-17-2-cache-{label}"}}, context=CONTEXT)
    print("cache", label, "policy_body_runs", durable.POLICY_CALLS)
