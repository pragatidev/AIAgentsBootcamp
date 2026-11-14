# %%
"""Lab 18.2: run the desk through the Agent Server, then open it in Studio.

What we build: a small client for the DataFlow refund desk that talks to the Agent Server instead of calling the
graph in this process. The lab starts `langgraph dev` (the server that serves every graph langgraph.json names, on one
port), and the client you type starts a thread on the desk, streams a refund run until it parks at the reviewer's
question, reads the thread's saved state from the server, and resumes it with the reviewer's answer. The same server
is the one Studio draws. It stops after the approval; set STUDIO_HOLD_SECONDS to keep it up for the Studio link.

What you learn: langgraph.json is the menu. Each graph id on it (desk, team, nightly, replay) points at a file and a
variable, and the server keeps every thread's checkpoints itself, which is why the served desk is compiled with no
checkpointer of its own. A client never holds the graph: it holds a thread id and a graph id, and the server does the
rest, so a run that parks stays parked on the server until anyone, this client or a reviewer clicking in Studio,
sends the answer. A resume is a command, {"resume": "approve"}, sent to the same thread. And this server is for
development: it keeps everything in memory and in a folder under the project, and a real deployment needs persistent
storage. The lab starts the server for you and always stops it, so nothing is left running on the port.

What will be true on your screen: the model line and the versions, with the langgraph-api and langgraph-sdk the
server and the client run on; the four graph ids served and the desk's four nodes; the server's API, Studio and docs
URLs and the langgraph-api version the server names in its own log; the four assistants; then T-3001 through the
server: classify's update, the pause, next ['refund'], the reviewer's question, no refund row; the approval: the
reply "Refund issued for order DF-1001. Amount: 49.0.", next [], the thread's checkpoints, one refund row; and last,
the server stopped and the port free.
"""

from importlib.metadata import version
from pathlib import Path
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph_sdk import get_sync_client

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.ops.dev_server import dev_port, dev_server, port_in_use
from dataflow.tools.refund import get_refunds_path, read_refunds

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))
print("langgraph-api", version("langgraph-api"))
print("langgraph-sdk", version("langgraph-sdk"))

# %%
# The menu the server reads, and the desk's nodes as Studio will draw them (the server's classify calls the same
# config.get_chat_model() this lab printed above).
served = json.loads((root / "langgraph.json").read_text(encoding="utf-8"))["graphs"]
for graph_id, target in served.items():
    print("served", graph_id, target)
nodes = [name for name in build_v4_hitl(for_server=True).get_graph().nodes if not name.startswith("__")]
print("desk_nodes", nodes)
GRAPH_ID = "desk"


# %%
# TYPE THIS: run_to_the_pause and answer. The signatures and docstrings are given; you type the rest.
# The package has no server client; tests/test_dataflow_hitl.py checks the same park and resume with invoke.
def run_to_the_pause(client, graph_id, ticket_text):
    """Start a thread on the served graph, stream the run until it stops, print where it stopped. Return the thread id."""
    thread_id = client.threads.create()["thread_id"]
    for part in client.runs.stream(thread_id, graph_id, input={"ticket": ticket_text}, stream_mode="updates"):
        if part.event == "updates":
            print("update", list(part.data))
    state = client.threads.get_state(thread_id)
    print("next", state["next"])
    for task in state["tasks"]:
        for item in task["interrupts"]:
            print("question", item["value"]["question"])
    return thread_id


def answer(client, thread_id, graph_id, decision):
    """Resume the parked thread with the reviewer's decision. Print the reply, what is left to run, the checkpoints."""
    final = client.runs.wait(thread_id, graph_id, command={"resume": decision})
    print("reply", final["reply"])
    state = client.threads.get_state(thread_id)
    print("next", state["next"])
    history = client.threads.get_history(thread_id, limit=20)
    print("checkpoints", len(history))
    return final


# BREAK: change GRAPH_ID = "desk" to GRAPH_ID = "desks", a graph id langgraph.json does not serve, and run. The
# server is up and lists its four assistants; the thread is created, then the stream call is refused with status 422,
# langgraph_sdk.errors.UnprocessableEntityError: Invalid assistant: 'desks'. Must be either a valid assistant UUID or
# one of the registered graphs: desk, team, nightly, replay. Nothing ran, no refund row, and the with block still
# stops the server on the way out. Put it back and run.

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = [json.loads(line) for line in tickets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
ticket = {row["ticket_id"]: row for row in rows}["T-3001"]
print("ticket", ticket["ticket_id"], ticket["text"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
port = dev_port()
hold = int(os.environ.get("STUDIO_HOLD_SECONDS", "0"))

with dev_server(root, port) as server:
    print("api", server.base_url)
    print("studio", server.studio_url)
    print("docs", server.docs_url)
    print("served_by langgraph-api", server.api_version)
    client = get_sync_client(url=server.base_url)
    print("assistants", sorted(item["graph_id"] for item in client.assistants.search()))
    thread_id = run_to_the_pause(client, GRAPH_ID, ticket["text"])
    print("rows_while_parked", len(read_refunds()))
    print("reviewer answers approve")
    answer(client, thread_id, GRAPH_ID, "approve")
    print("refunds_rows", len(read_refunds()))
    if hold:
        print("studio_open_for_seconds", hold, "thread", thread_id)
        time.sleep(hold)

print("server_stopped port", port, "free", not port_in_use(port))
