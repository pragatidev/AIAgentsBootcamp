# %% [markdown]
# Break for lab 5.3: the same graph and checkpointer, a different thread id.
#
# The first invoke tells the desk a name and an order on thread lab-5-3.
# The second invoke asks for them on thread lab-5-3-other. The desk is a
# stranger there: human_count is 1 and knows_priya is False. That is the
# design, not a bug: a thread is one conversation.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

import config

SYSTEM = (
    "You are the DataFlow support desk. Answer in one or two short sentences. "
    "When the customer already told you a name or an order id on this thread, use it."
)


class S(TypedDict):
    messages: Annotated[list, add_messages]


def chat(state):
    m = config.get_local_chat_model(reasoning=False, num_predict=80)
    r = m.invoke([SystemMessage(content=SYSTEM), *state["messages"]])
    return {"messages": [AIMessage(content=str(r.content))]}


b = StateGraph(S)
b.add_node("chat", chat)
b.add_edge(START, "chat")
b.add_edge("chat", END)
g = b.compile(checkpointer=InMemorySaver())

# %%
g.invoke(
    {"messages": [HumanMessage(content="My name is Priya. This is about order DF-1001.")]},
    {"configurable": {"thread_id": "lab-5-3"}},
)
out = g.invoke(
    {"messages": [HumanMessage(content="What is my name, and which order were we talking about?")]},
    {"configurable": {"thread_id": "lab-5-3-other"}},
)
print("thread", "lab-5-3-other")
print("reply", out["messages"][-1].content)
print("human_count", sum(1 for m in out["messages"] if m.type == "human"))
print("knows_priya", "Priya" in out["messages"][-1].content)
