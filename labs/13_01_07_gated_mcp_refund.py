# %%
"""Lab 29.8: a destructive MCP tool behind approval.

What we build: a person in front of anything an MCP tool might change, decided by what the tool is and
who vouches for it. You type needs_approval: a tool runs without a person only when its server is on the
company's allowlist and that server says the tool only reads. The desk is the create_agent desk with
LangChain's human-in-the-loop middleware, the gate you built in lab 4.14, keyed on every bound tool that
needs approval. Then the orders server is stopped and started again between a park and its approval.

What you learn: an annotation is a claim made by whoever wrote the server. The specification says a
client should never decide tool use from the annotations of a server it does not trust, and its defaults
are read-only false and destructive true; needs_approval follows them. And a wait that must survive a
restart belongs to your desk's thread and its checkpointer: revision 2026-07-28 has no protocol session,
so there is nothing on the server to lose.

What will be true on your screen: the versions and the approved servers; each tool with its server, its
read-only claim and whether it parks; a refund that parks with its payload, denied on thread A with no
ledger row and approved on thread B with one; a lookup that never parks; a refund parked on thread C, the
orders server stopped and started again under a new process id, then approved, and the row landing; and
the unlisted helper's mark_resolved parking although it claims to only read.

The model here is a stand-in that always asks for the same call, so the gate is the only thing that
decides.
"""

# Run this one from the terminal: `python labs/13_01_07_gated_mcp_refund.py`.
# no-twin: an MCP stdio client starts the server as a subprocess and needs a real stderr handle, which a Jupyter kernel does not have.

from pathlib import Path
from importlib.metadata import version
import os
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")

from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig, ToolCallLimitMiddleware
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from dataflow.mcp.allowlist import approved_servers, server_name
from dataflow.mcp.bind import bind_mcp_tools, build_desk, close_mcp
from dataflow.mcp.client import load_config
from dataflow.mcp.fixtures.helper_server import helper, read_resolved
from dataflow.mcp.gate import describe_call
from dataflow.mcp.server import PID_PATH
from dataflow.rag.desk import TOOL_RUN_LIMIT, reply_text
from dataflow.tools.refund import read_refunds

print("mcp", version("mcp"), "fastmcp", version("fastmcp"), "langchain", version("langchain"), "langgraph", version("langgraph"))

# The refund and mark_resolved write rows. Temp files keep the real ledger clean; stdio_env() passes the
# refunds path on to the server process.
for key, prefix in (("DATAFLOW_REFUNDS_PATH", "refunds-"), ("DATAFLOW_RESOLVED_PATH", "resolved-")):
    handle = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".jsonl", delete=False)
    handle.close()
    os.environ[key] = handle.name

trusted = approved_servers()
print("approved_servers", sorted(trusted))


# %%
# TYPE THIS: needs_approval. The signature and docstring are given; you type the body.
# Its finished copy is needs_approval in dataflow/mcp/gate.py, beside approval_gate.
def needs_approval(tool, trusted_servers: set) -> bool:
    """Park this tool unless it comes from an approved server that says it only reads."""
    mcp = (tool.metadata or {}).get("mcp") or {}
    server = mcp.get("server", {}).get("name")
    read_only = (mcp.get("tool", {}).get("annotations") or {}).get("read_only_hint") is True
    return not (server in trusted_servers and read_only)


# BREAK: replace the return line above with return not read_only, which trusts every server's word, and
# run. mark_resolved, from a helper server nobody approved, claims to only read: it runs without parking
# and writes a row. Put the line back and run.


# %%
def bind_orders() -> list:
    """Start the orders server over stdio and bind its tools. close_mcp() stops it."""
    return bind_mcp_tools(load_config(sys.executable))


def server_pid() -> str:
    return PID_PATH.read_text(encoding="utf-8").strip() if PID_PATH.is_file() else "none"


tools = bind_orders() + bind_mcp_tools(helper)
for tool in tools:
    claim = tool.metadata["mcp"]["tool"].get("annotations") or {}
    print("tool", tool.name, "server", server_name(tool), "claims", claim, "parks", needs_approval(tool, trusted))


def gate_for(tools: list) -> HumanInTheLoopMiddleware:
    gated = [tool.name for tool in tools if needs_approval(tool, trusted)]
    rule = InterruptOnConfig(allowed_decisions=["approve", "reject"], description=describe_call)
    return HumanInTheLoopMiddleware(interrupt_on={name: rule for name in gated})


print("gated", sorted(gate_for(tools).interrupt_on))
print("orders_server_pid", server_pid())


# %%
# A stand-in model that asks for one call and then says it is done.
class AsksFor(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def asks(name: str, args: dict) -> AsksFor:
    call = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "c1", "type": "tool_call"}])
    return AsksFor(responses=[call, AIMessage(content="Done.")])


saver = InMemorySaver()  # the desk's memory of parked runs, by thread id; it outlives the MCP server
REFUND = ("refund", {"order_id": "DF-1001", "amount": 49.0, "reason": "unused lamp"})


def desk(model, tools):
    return build_desk(model=model, tools=tools, middleware=[gate_for(tools), ToolCallLimitMiddleware(run_limit=TOOL_RUN_LIMIT, exit_behavior="end")], checkpointer=saver)


def start(desk, thread: str, text: str) -> list:
    out = desk.invoke({"messages": [HumanMessage(content=text)]}, {"configurable": {"thread_id": thread}})
    requests = out["__interrupt__"][0].value["action_requests"] if out.get("__interrupt__") else []
    print(thread, "parked", [r["name"] for r in requests])
    for request in requests:
        print(thread, "payload", request["description"])
    if not requests:
        print(thread, "ran", [m.name for m in out["messages"] if m.type == "tool"], "reply", reply_text(out))
    return requests


def decide(desk, thread: str, decision: dict) -> None:
    out = desk.invoke(Command(resume={"decisions": [decision]}), {"configurable": {"thread_id": thread}})
    print(thread, decision["type"], "reply", reply_text(out))


# %%
try:
    refund_desk = desk(asks(*REFUND), tools)
    start(refund_desk, "thread-A", "Refund DF-1001, the lamp is unused.")
    decide(refund_desk, "thread-A", {"type": "reject", "message": "Not eligible: opened."})
    print("thread-A ledger_rows", len(read_refunds()))

    refund_desk = desk(asks(*REFUND), tools)
    start(refund_desk, "thread-B", "Refund DF-1001, the lamp is unused.")
    decide(refund_desk, "thread-B", {"type": "approve"})
    print("thread-B ledger_rows", len(read_refunds()))

    start(desk(asks("lookup_order", {"order_id": "DF-1002"}), tools), "thread-lookup", "Where is DF-1002?")

    # Park on thread C, then stop the orders server and start it again before anyone decides.
    start(desk(asks(*REFUND), tools), "thread-C", "Refund DF-1001, the lamp is unused.")
    pid_before = server_pid()
    close_mcp()
    deadline = time.time() + 10
    while PID_PATH.is_file() and time.time() < deadline:
        time.sleep(0.1)
    print("thread-C server_stopped", not PID_PATH.is_file())
    tools = bind_orders() + bind_mcp_tools(helper)
    print("thread-C server_pid", pid_before, "then", server_pid())
    print("thread-C server_restarted", server_pid() != pid_before and server_pid() != "none")
    decide(desk(AsksFor(responses=[AIMessage(content="The refund is done.")]), tools), "thread-C", {"type": "approve"})
    print("thread-C ledger_rows", len(read_refunds()))

    helper_desk = desk(asks("mark_resolved", {"order_id": "DF-1001"}), tools)
    requests = start(helper_desk, "thread-D", "Is the ticket for DF-1001 resolved?")
    if requests:
        decide(helper_desk, "thread-D", {"type": "reject", "message": "Unapproved server."})
    print("thread-D resolved_rows", len(read_resolved()))
finally:
    close_mcp()
    if PID_PATH.is_file():
        PID_PATH.unlink()
    print("pid_file_left", PID_PATH.is_file())
