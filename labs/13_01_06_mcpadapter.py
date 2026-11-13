# %%
"""Lab 28.8: bind MCP tools to the DataFlow desk with MCPAdapter.

What we build: the desk answering through MCP. You type mcp_tools, which opens LangChain's MCPAdapter on a
server and returns its tools as LangChain tools. Then the create_agent desk from Parts 2 and 3 gets those
tools in place of its local ones and answers "Where is order DF-1002?".

What you learn: the adapter is an MCP client that lives inside LangChain. FastMCP does the wire; out come
LangChain tools whose schema came from the server at run time and whose metadata says which server served
them and what it claims about each tool. The tools are async; dataflow/mcp/bind.py keeps their client's
connection on one long-lived event loop so the desk's plain invoke can call them. A string target must be
an http(s) URL, so a path typed as a string never quietly starts a process.

What will be true on your screen: the LangChainBetaWarning (langchain.mcp is beta in LangChain 1.4); each
tool's name, argument schema and metadata["mcp"] (the server's name and the read-only and destructive
hints); the desk's reply about DF-1002 and the tool it ran.
"""

# Run this one from the terminal: `python labs/13_01_06_mcpadapter.py`.
# no-twin: an MCP stdio client starts the server as a subprocess and needs a real stderr handle, which a Jupyter kernel does not have.

from pathlib import Path
import json
import os
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")

from langchain.mcp import MCPAdapter

import config
from dataflow.mcp.bind import bind_mcp_tools, bound_names, build_desk, close_mcp
from dataflow.mcp.client import load_config
from dataflow.mcp.runtime import run_async
from dataflow.mcp.server import PID_PATH
from dataflow.rag.desk import ask_desk, reply_text


# %%
# TYPE THIS: mcp_tools. The signature and docstring are given; you type the body.
# Its finished copy is _open_and_list in dataflow/mcp/bind.py, which also keeps the adapter open.
async def mcp_tools(target) -> list:
    """Open an MCPAdapter on target and return the server's tools as LangChain tools."""
    async with MCPAdapter(target) as adapter:
        return await adapter.list_tools()


# %%
cfg = load_config(sys.executable)
# The listing below needs the server only while it lists; let it stop when the adapter closes.
cfg["mcpServers"]["dataflow"]["keep_alive"] = False
server_target = cfg

# BREAK: replace cfg on the line above with the string "dataflow/mcp/server.py" and run. The adapter refuses
# it with a ValueError before anything starts: a string must be an http(s) URL, because a string from a
# config file or from a model must not quietly launch a process. Pass a Path or the config dict instead.

try:
    tools = run_async(mcp_tools(server_target))
except ValueError as exc:
    tools = []
    print("adapter_refused", type(exc).__name__, exc)
for tool in tools:
    schema = tool.args_schema if isinstance(tool.args_schema, dict) else tool.args_schema.model_json_schema()
    print("tool", tool.name)
    print("  args_schema", json.dumps(schema))
    print("  metadata_mcp", json.dumps(tool.metadata["mcp"]))

# %%
model = config.get_chat_model()
print("model", type(model).__name__, getattr(model, "model", None) or getattr(model, "model_name", None))
try:
    bound = bind_mcp_tools(cfg)
    print("bound_names", bound_names(bound))
    desk = build_desk(model=model, tools=bound)
    state = ask_desk(desk, "Where is order DF-1002?")
    ran = [(call["name"], call["args"]) for m in state["messages"] for call in (getattr(m, "tool_calls", None) or [])]
    print("tools_ran", ran)
    print("reply", reply_text(state))
finally:
    close_mcp()
    if PID_PATH.is_file():
        PID_PATH.unlink()
    print("pid_file_left", PID_PATH.is_file())
