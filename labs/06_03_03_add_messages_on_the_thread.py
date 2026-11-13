# %%
"""Lab 12.3: add_messages on the DataFlow thread.

What we build: you type the chat desk's notebook, ChatState, whose one key is the conversation with the
add_messages reducer on it, and build_chat: two nodes that each return only the message they add (the
agent's answer, then a desk note), wired START, agent, take_note, END, and compiled with a checkpointer.
Then one customer's two tickets, T-3001 and the follow-up T-3028, go through it on one thread.

What you learn: a reducer decides what a write to a key does. With add_messages a node returns only its new
message and the reducer appends it, so the conversation grows on the thread, turn after turn, without any
node copying the history. A message whose id is already in the list is not added: it replaces the old one in
place, which is how you correct a message. Without the reducer the key keeps only the last write, so every
node and every turn wipes out what came before, and nothing fails to tell you.

What will be true on your screen: the model line and the versions; for turn one the count after the input,
the agent and the note (1, 2, 3, the newest message a human, an ai, then the ai named note); turn two going on
from there (4, 5, 6); the whole thread with each message's role; then the note replaced by its id: the count
stays 6 and the last message is the edited note with the same id.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys
from typing import Annotated, TypedDict

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.messages import AGENT_SYSTEM

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: ChatState and build_chat. The signature and docstring are given; you type the rest.
# The package's finished version is MessagesState, take_note and build_messages_graph in dataflow/graphs/messages.py.
class ChatState(TypedDict):
    """One key, the conversation. add_messages appends each write and replaces a message whose id it already holds."""
    messages: Annotated[list, add_messages]


def build_chat(model=None, checkpointer=None):
    """agent answers, take_note adds a desk note; each returns only its new message. model: else the run's context, else config."""

    def agent(state: ChatState, runtime: Runtime[DeskContext] | None = None) -> dict:
        context = runtime.context if runtime is not None else None
        llm = model if model is not None else getattr(context, "model", None) or config.get_chat_model()
        answer = llm.invoke([SystemMessage(content=AGENT_SYSTEM), *state["messages"]])
        return {"messages": [answer]}

    def take_note(state: ChatState) -> dict:
        humans = [message for message in state["messages"] if message.type == "human"]
        snippet = str(humans[-1].content).replace("\n", " ").strip()[:80] if humans else ""
        return {"messages": [AIMessage(content=f"desk note: recorded the ticket ({snippet})", name="note")]}

    builder = StateGraph(ChatState, context_schema=DeskContext)
    builder.add_node("agent", agent)
    builder.add_node("take_note", take_note)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", "take_note")
    builder.add_edge("take_note", END)
    return builder.compile(checkpointer=checkpointer)


# BREAK: change the key to messages: list (no reducer) and run. Nothing fails. Each write now replaces the whole
# list, so the count prints 1 after every step of both turns, the thread ends as one message, the desk note of a
# ticket it can no longer see, and the replace cell has nothing left to replace but that note. Put it back and run.

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
graph = build_chat(model=chat, checkpointer=InMemorySaver())
thread = {"configurable": {"thread_id": "lab-12-3"}}
print("nodes", list(graph.get_graph().nodes))

for turn, ticket_id in enumerate(["T-3001", "T-3028"], start=1):
    text = by_id[ticket_id]["text"]
    print("turn", turn, ticket_id, by_id[ticket_id]["customer_id"], text)
    for values in graph.stream({"messages": [HumanMessage(content=text)]}, thread, stream_mode="values"):
        newest = values["messages"][-1]
        print("  count", len(values["messages"]), "newest", newest.type, newest.name or "")

# %%
messages = graph.get_state(thread).values["messages"]
print("thread_count", len(messages))
for index, message in enumerate(messages):
    print(index, message.type, message.name or "", str(message.content).replace("\n", " "))

# %%
# A write whose id is already on the thread replaces that message instead of adding one.
note = messages[-1]
print("note_id", note.id)
graph.update_state(thread, {"messages": [AIMessage(content="desk note: warranty question sent to the orders team", id=note.id, name="note")]})
after = graph.get_state(thread).values["messages"]
print("count_after_replace", len(after))
print("last", after[-1].name, after[-1].content)
print("same_id", after[-1].id == note.id)
