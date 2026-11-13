# %%
"""Lab 28.9: two servers on one desk.

What we build: a desk that uses two teams' servers. The orders team's server is the one you built; the
knowledge team's server, dataflow/mcp/kb_server.py, serves DataFlow's retrieve over MCP. You type the
host's config with two named servers, orders and kb. The desk answers an order question through one and a
returns question through the other, and then a person's approval is put in front of the refund.

What you learn: a host makes one client per server. FastMCP's ClientGroup does exactly that and names each
tool after its server, server_tool, so two servers can never collide: lookup_order arrives as
orders_lookup_order. Anything keyed by tool names, a system prompt or an approval list, has to be built
from the names the desk actually bound. Lab 4.14 showed a gate is only as good as its list; here the list
goes stale without anyone touching it.

What will be true on your screen: the three prefixed names and the protocol revision each client
negotiated; the order question reaching orders_lookup_order and the returns question reaching kb_retrieve,
with their replies; and a refund that parks before it writes, with no ledger row until a person approves.
"""

# Run this one from the terminal: `python labs/13_01_09_two_servers.py`.
# no-twin: an MCP stdio client starts the server as a subprocess and needs a real stderr handle, which a Jupyter kernel does not have.

from pathlib import Path
import os
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")

from fastmcp.client.group import ClientGroup
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import config
from dataflow.mcp.bind import bind_mcp_tools, bound_names, build_desk, close_mcp
from dataflow.mcp.client import ROOT, stdio_env
from dataflow.mcp.runtime import run_async
from dataflow.mcp.server import PID_PATH
from dataflow.rag.desk import ask_desk, reply_text
from dataflow.tools.refund import read_refunds

# The refund writes a ledger row. A temp ledger keeps the real one clean; stdio_env() passes this to the child.
ledger = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
ledger.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = ledger.name


# %%
# TYPE THIS: two_servers. The signature and docstring are given; you type the body.
# Its one-server cousin is load_config in dataflow/mcp/client.py.
def two_servers() -> dict:
    """The host's config: two named servers, each started by this Python from the repo with the environment it needs."""

    def stdio(module: str) -> dict:
        return {"command": sys.executable, "args": ["-m", module], "cwd": str(ROOT), "env": stdio_env(), "transport": "stdio"}

    return {"mcpServers": {"orders": stdio("dataflow.mcp.server"), "kb": stdio("dataflow.mcp.kb_server")}}


# %%
# One client per server. Client(two_servers()) would instead build an in-process router in front of both and
# reuse one connection per server for every request (FastMCP logs that it "may cause context mixing").
group = ClientGroup.from_config(two_servers())


async def negotiated(group: ClientGroup) -> dict:
    """Connect every client in the group and read the revision each one agreed with its server."""
    async with group:
        return group.protocol_versions


def tools_ran(state: dict) -> list:
    return [(call["name"], call["args"]) for m in state["messages"] for call in (getattr(m, "tool_calls", None) or [])]


try:
    print("protocol_versions", run_async(negotiated(group)))
    tools = bind_mcp_tools(group)
    names = bound_names(tools)
    print("bound_names", names)
    print("served_by", {tool.name: tool.metadata["mcp"]["server"]["name"] for tool in tools})

    desk = build_desk(model=config.get_chat_model(), tools=tools)
    for question in ("Where is order DF-1002?", "How many days do I have to return an item?"):
        state = ask_desk(desk, question)
        print("question", question)
        print("  tools_ran", tools_ran(state))
        print("  reply", reply_text(state))

    # %%
    # The gate. A stand-in model that always asks for the refund, so the gate is the only thing that decides.
    class AlwaysRefunds(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    ask_refund = AIMessage(
        content="",
        tool_calls=[{"name": "orders_refund", "args": {"order_id": "DF-1001", "amount": 49.0, "reason": "unused lamp"}, "id": "r1", "type": "tool_call"}],
    )
    stand_in = AlwaysRefunds(responses=[ask_refund, AIMessage(content="The refund is done.")])

    def refund_gate(names: list[str]) -> HumanInTheLoopMiddleware:
        """Park before every refund tool the desk has bound, whatever prefix its server gave it."""
        gated = [name for name in names if name == "refund" or name.endswith("_refund")]
        return HumanInTheLoopMiddleware(interrupt_on={name: True for name in gated})

    # BREAK: replace the gated line above with gated = ["refund"], the bare name lab 4.14 would have typed, and
    # run. The desk's tool is orders_refund, so nothing parks: the refund runs at once and writes a ledger row.
    # Put the line back and run.

    gate = refund_gate(names)
    print("gated", sorted(gate.interrupt_on))
    gated_desk = build_desk(model=stand_in, tools=tools, middleware=[gate], checkpointer=InMemorySaver())
    thread = {"configurable": {"thread_id": "lab-28-9-refund"}}
    out = gated_desk.invoke({"messages": [HumanMessage(content="Please refund order DF-1001, the lamp is unused.")]}, thread)
    parked = out.get("__interrupt__")
    print("refund_parked", bool(parked))
    if parked:
        print("parked_on", [request["name"] for request in parked[0].value["action_requests"]])
    print("ledger_rows_before_decision", len(read_refunds()))
    if parked:
        out = gated_desk.invoke(Command(resume={"decisions": [{"type": "approve"}]}), thread)
        print("ledger_rows_after_approve", len(read_refunds()))
    print("reply", reply_text(out))
finally:
    close_mcp()
    if PID_PATH.is_file():
        PID_PATH.unlink()
    print("pid_file_left", PID_PATH.is_file())
