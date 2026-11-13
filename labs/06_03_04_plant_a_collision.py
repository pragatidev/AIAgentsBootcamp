# %%
"""Lab 12.4: plant a collision, read the error, fix it with a reducer.

What we build: a graph where two nodes write the same key in the same step. START has two edges, one to
write_a (it looks up order DF-1001 and adds a log line) and one to write_b (it reads the return policy and
adds a log line), so both run in one superstep and both write log. You type the fixed notebook, FixedState,
whose log key carries operator.add, the two writers, each returning a one-item list, and build_fixed. Then
you plant the collision yourself by taking the reducer off.

What you learn: the annotation on a key decides its channel. A plain key keeps one value, and the channel
accepts only one write per step; two writes in the same step raise InvalidUpdateError, on purpose, because
LangGraph will not pick a winner for you. Annotated[list[str], operator.add] makes the key a channel that
folds every write in with +, so both lines land. Section 16 runs nodes side by side for real, and every one
of those graphs stands on this.

What will be true on your screen: the model line (none: no model is called) and the versions, the drawing
with START fanning out to write_a and write_b, the log channel's class (BinaryOperatorAggregate), then both
log lines, orders looked up and policy read. With the break, the class is LastValue and the run stops on
InvalidUpdateError: At key 'log': Can receive only one value per step.
"""

from importlib.metadata import version
from pathlib import Path
import operator
import sys
from typing import Annotated, TypedDict

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.graph import END, START, StateGraph

from dataflow.tools.orders import lookup_order_by_id
from dataflow.tools.policy import read_policy

print("model none: this run calls no model")
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: FixedState, write_a, write_b and build_fixed. The signatures and docstrings are given; you type the rest.
# The package's finished version is ReducedState, write_a_list, write_b_list and build_collision_fixed in
# dataflow/graphs/collision.py (its build_collision is the planted one, a plain log key).
class FixedState(TypedDict):
    """The ticket, and a log that both writers add a line to in the same step."""
    ticket: str
    log: Annotated[list[str], operator.add]


def write_a(state: FixedState) -> dict:
    """Look up the order, then add one log line."""
    lookup_order_by_id("DF-1001")
    return {"log": ["orders looked up"]}


def write_b(state: FixedState) -> dict:
    """Read the return policy, then add one log line."""
    read_policy("return")
    return {"log": ["policy read"]}


def build_fixed():
    """Two edges from START, so write_a and write_b run in the same superstep."""
    builder = StateGraph(FixedState)
    builder.add_node("write_a", write_a)
    builder.add_node("write_b", write_b)
    builder.add_edge(START, "write_a")
    builder.add_edge(START, "write_b")
    builder.add_edge("write_a", END)
    builder.add_edge("write_b", END)
    return builder.compile()


# BREAK: change the log line of FixedState to log: list[str] (take the reducer off) and run. It compiles, the
# channel line now says LastValue, and the run stops on InvalidUpdateError: At key 'log': Can receive only one
# value per step. Use an Annotated key to handle multiple values. Read it line by line: which key, why, and the
# fix it names. Put it back and run.

# %%
graph = build_fixed()
print(graph.get_graph().draw_mermaid())
print("log_channel", type(graph.channels["log"]).__name__)

# %%
out = graph.invoke({"ticket": "DF-1001", "log": []})
print("log_lines", len(out["log"]))
for line in out["log"]:
    print("log", line)
