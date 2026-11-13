# %%
"""Lab 14.2: park the refund tool for approval.

What we build: the refund node of the DataFlow v4 desk, typed by you. It looks up the order, finds the policy line,
builds a payload a reviewer can decide from, and calls interrupt(payload). The run stops there and saves. When the
reviewer answers on the same thread, the node starts again from its first line, interrupt() hands back the answer,
and only then does the node write: a refund row on approve, a decline on reject, nothing on an answer it cannot read.
The rest of the desk (the classifier, the router, the lookup and policy nodes) is given, so the refund node is the
only new thing on the road.

What you learn: interrupt() is a pause, not a crash, and the pause has one rule that decides where every line goes.
On resume the node runs again from the top, so everything above interrupt() runs twice: once before the pause and
once after the answer. A lookup or a policy search can run twice and nothing happens. A write cannot. That is why
the write sits below interrupt(), and the BREAK shows what a single line in the wrong place does to the ledger.

What will be true on your screen: the model line and the versions, then T-3001: the route refund, the payload with
order DF-1001, 49.0, the policy line and the question, the thread waiting at ('refund',) with no refund row; then the
reviewer's approve on the same thread, the reply "Refund issued for order DF-1001. Amount: 49.0.", one refund row,
and nothing left to run.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

import config
from dataflow.graphs.v4_hitl import HitlState, _parse_decision, classify, lookup_node, pick_route, policy_node
from dataflow.tools.orders import lookup_order_from_ticket
from dataflow.tools.policy import search_policy
from dataflow.tools.refund import decline_refund, get_refunds_path, issue_refund, read_refunds

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: refund_node. The signature and docstring are given; you type the rest.
# The package's finished version is refund_node in dataflow/graphs/v4_hitl.py (lines 159 to 249).
def refund_node(state):
    """Build the reviewer's payload, park on it, and write only after a person said approve."""
    ticket = state.get("ticket", "")
    order = lookup_order_from_ticket(ticket)
    hit = search_policy.invoke({"question": ticket})
    amount = float(state.get("refund_amount") or order.get("amount") or 0)
    order_id = str(order.get("order_id") or "")
    payload = {
        "action": "refund",
        "ticket": ticket,
        "order_id": order_id,
        "amount": amount,
        "amount_source": "state" if state.get("refund_amount") else "order",
        "policy": str(hit.get("paragraph") or hit.get("reason") or "no customer policy matched"),
        "question": f"Approve this refund of {amount} on order {order_id}?",
    }
    decision = interrupt(payload)
    action, paid = _parse_decision(decision, amount)
    if action == "approve":
        record = issue_refund.invoke({"order_id": order_id, "amount": paid, "reason": "reviewer approved"})
        reply = f"Refund issued for order {order_id}. Amount: {record['amount']}."
    elif action == "reject":
        record = decline_refund.invoke({"order_id": order_id, "reason": "reviewer rejected the refund"})
        reply = f"Refund declined for order {order_id}. Reason: {record['reason']}"
    else:
        record = {"refunded": False, "unclear": True, "order_id": order_id, "answer": decision}
        reply = f"Refund not issued for order {order_id}: reviewer answer not understood ({decision})"
    return {"order": order, "decision": decision, "refund": record, "reply": reply}


# BREAK: add one line just above decision = interrupt(payload), at the same indent:
#     issue_refund.invoke({"order_id": order_id, "amount": amount, "reason": "written before anyone approved"})
# and run. rows_while_parked is 1: money went out before anyone answered. After approve the ledger has three rows:
# the added line ran a second time when the node started again from the top, then the approved write. Put it back
# and run.


# %%
def build_desk(refund, model):
    """The v4 desk with your refund node: classify, then lookup, policy or refund, then the end."""
    builder = StateGraph(HitlState)
    builder.add_node("classify", lambda state: classify(state, model=model))
    builder.add_node("lookup", lookup_node)
    builder.add_node("policy", policy_node)
    builder.add_node("refund", refund)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges("classify", pick_route, {"lookup": "lookup", "refund": "refund", "policy": "policy"})
    for name in ("lookup", "policy", "refund"):
        builder.add_edge(name, END)
    return builder.compile(checkpointer=InMemorySaver())


tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = [json.loads(line) for line in tickets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
ticket = {row["ticket_id"]: row for row in rows}["T-3001"]
print("ticket", ticket["ticket_id"], ticket["text"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
print("refunds_path", refunds_path.relative_to(root).as_posix() if refunds_path.is_relative_to(root) else refunds_path)

# %%
graph = build_desk(refund_node, chat)
thread = {"configurable": {"thread_id": "lab-14-2"}}
parked = graph.invoke({"ticket": ticket["text"]}, thread)
print("route", parked.get("route"))
waiting = graph.get_state(thread)
print("thread_next", waiting.next)
if waiting.interrupts:
    for key, value in waiting.interrupts[0].value.items():
        print("payload", key, value)
print("rows_while_parked", len(read_refunds()))

# %%
if waiting.interrupts:
    print("reviewer answers approve")
    done = graph.invoke(Command(resume="approve"), thread)
    print("reply", done.get("reply"))
for row in read_refunds():
    print("refund_row", row)
print("refunds_rows", len(read_refunds()))
print("thread_next", graph.get_state(thread).next)
