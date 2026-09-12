# %% [markdown]
# Thread memory: the conversation that remembers within a run.
#
# Two turns on one thread with an InMemorySaver. The second turn uses
# the first. Print both replies.

# %%
from pathlib import Path
import sys
from typing import Annotated, TypedDict

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

import config

SYSTEM = (
    "You are the DataFlow support desk. Answer in one or two short sentences. "
    "When the customer already told you a name or an order id on this thread, use it."
)


class ThreadState(TypedDict):
    messages: Annotated[list, add_messages]


def chat(state: ThreadState) -> dict:
    model = config.get_local_chat_model(reasoning=False, num_predict=80)
    result = model.invoke([SystemMessage(content=SYSTEM), *state["messages"]])
    return {"messages": [AIMessage(content=str(result.content))]}


# %%
builder = StateGraph(ThreadState)
builder.add_node("chat", chat)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)
graph = builder.compile(checkpointer=InMemorySaver())
thread = {"configurable": {"thread_id": "lab-5-3"}}

turn_one = graph.invoke(
    {
        "messages": [
            HumanMessage(content="My name is Priya. This is about order DF-1001.")
        ]
    },
    thread,
)
print("turn", 1)
print("reply_1", turn_one["messages"][-1].content)

# %%
turn_two = graph.invoke(
    {
        "messages": [
            HumanMessage(content="What is my name, and which order were we talking about?")
        ]
    },
    thread,
)
print("turn", 2)
print("reply_2", turn_two["messages"][-1].content)
print("human_count", sum(1 for m in turn_two["messages"] if m.type == "human"))
print("second_turn_used_first", "Priya" in str(turn_two["messages"][-1].content))
