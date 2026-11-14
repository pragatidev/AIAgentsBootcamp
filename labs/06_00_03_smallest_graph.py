# %%
"""Lab 9.3: the smallest graph, every piece of the picture seen working once.

What we build: a graph with a two-key notebook (the state), two nodes and three fixed edges, START to
classify to reply to END, compiled with an in-memory checkpointer, then run on thread t1 and on thread t2.
No model is called, so it runs on any machine in about a second.

What you learn: a node is a plain function that reads the notebook and returns only the lines it changes;
compile() turns the drawing into something you can run; after every step the checkpointer saves the
notebook under the thread id, which is what pause, resume and time travel later stand on; and two thread
ids are two notebooks that never share a line.

What will be true on your screen: the model line (none), the langchain-core and langgraph versions, the
nodes and the drawing, then for t1 the final state, the saved notebook from get_state, its next node (none,
the run finished), every saved checkpoint with its step, the count of them, and then t2's own notebook
beside t1's, untouched.
"""

from importlib.metadata import version
from pathlib import Path
import sys
from typing import TypedDict

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

print("model none: this run calls no model")
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# The notebook: two keys. The ticket comes in; each node adds to the note.
class Note(TypedDict, total=False):
    ticket: str
    note: str


def classify(state: Note) -> dict:
    """Reads the ticket, returns the one line it changes."""
    kind = "an order" if "DF-" in state["ticket"] else "a question"
    return {"note": f"classify saw {kind}"}


def reply(state: Note) -> dict:
    """Reads the note classify wrote, returns it with its own words added."""
    return {"note": state["note"] + "; reply answered"}


builder = StateGraph(Note)
builder.add_node("classify", classify)
builder.add_node("reply", reply)
builder.add_edge(START, "classify")
builder.add_edge("classify", "reply")
builder.add_edge("reply", END)
graph = builder.compile(checkpointer=InMemorySaver())
print("nodes", list(graph.get_graph().nodes))
print(graph.get_graph().draw_mermaid())

# %%
# Thread t1: run, then read what the checkpointer saved for it.
t1 = {"configurable": {"thread_id": "t1"}}
final = graph.invoke({"ticket": "Where is order DF-1002?"}, t1)
print("t1 final", final)
saved = graph.get_state(t1)
print("t1 saved", saved.values)
print("t1 next", saved.next)
history = list(graph.get_state_history(t1))
for snapshot in reversed(history):
    print("t1 checkpoint step", snapshot.metadata["step"], "next", snapshot.next, "values", snapshot.values)
print("t1 checkpoints", len(history))

# %%
# Thread t2: same graph, another thread id, another notebook.
t2 = {"configurable": {"thread_id": "t2"}}
print("t2 final", graph.invoke({"ticket": "What is your return window?"}, t2))
print("t2 saved", graph.get_state(t2).values)
print("t1 saved again", graph.get_state(t1).values)
print("threads share state", graph.get_state(t1).values == graph.get_state(t2).values)
