# %%
"""Lab 28.7: call the server from a client.

What we build: a client in your process and the DataFlow server in another, on the two ends of a stdio
wire. You type call_lookup: open a FastMCP Client on a config, list the tools, call lookup_order, and
return what came back with the protocol revision the two sides agreed on.

What you learn: a host's config names each server and says how to start it (command, args, cwd, env,
transport). The client starts the server as a child process, and a stdio child sees only a short
allowlist of your environment (PATH, SYSTEMROOT, TEMP and a few more on Windows; HOME, PATH, SHELL and a
few more elsewhere), not your PYTHONPATH and not your .env. A host starts its servers from its own
folder, so the config has to carry everything the server needs.

What will be true on your screen: the command as client_config.json has it and as it is filled at run
time, the folder and the environment keys the child gets, the negotiated protocol_version 2026-07-28, the
two tools, DF-1001's row, the runs file written and then restored, and no pid file left behind.
"""

# Run this one from the terminal: `python labs/13_01_04_mcp_client.py`.
# no-twin: an MCP stdio client starts the server as a subprocess and needs a real stderr handle, which a Jupyter kernel does not have.

from pathlib import Path
import json
import os
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")

from fastmcp import Client

from dataflow.mcp.client import CONFIG_PATH, RUNS_PATH, stdio_env
from dataflow.mcp.runtime import run_async
from dataflow.mcp.server import PID_PATH

committed_run = RUNS_PATH.read_text(encoding="utf-8") if RUNS_PATH.is_file() else ""


# %%
# TYPE THIS: call_lookup. The signature and docstring are given; you type the body.
# Its finished copy is _call in dataflow/mcp/client.py.
async def call_lookup(config: dict, order_id: str, timeout: float = 30) -> dict:
    """Start the server from config, list its tools and look up one order; return the revision, the names and the row."""
    async with Client(config, timeout=timeout, init_timeout=timeout) as client:
        tools = await client.list_tools()
        result = await client.call_tool("lookup_order", {"order_id": order_id})
        return {"protocol_version": client.protocol_version, "tools": [tool.name for tool in tools], "result": result.data}


# %%
config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
server = config["mcpServers"]["dataflow"]
print("config_command_was", server["command"], " ".join(server["args"]))
# "python" in the file could be any Python on the machine; this one has the course installed.
server["command"] = sys.executable
# A host such as Claude Desktop starts the server from its own folder, not from your repo. This lab does the same.
server["cwd"] = tempfile.gettempdir()
server["env"] = stdio_env()
# FastMCP keeps a stdio server running after the client leaves, to reuse it. This one should stop when the call is done.
server["keep_alive"] = False
print("config_command_now", server["command"], " ".join(server["args"]))
print("child_cwd", server["cwd"])
print("child_env_keys", sorted(server.get("env", {})))

# BREAK: delete the line server["env"] = stdio_env() above and run. The child starts in the temp folder with
# only the short allowlist, cannot import dataflow and exits at once: the client reports the connection
# closed in well under ten seconds, and the child's ModuleNotFoundError prints on stderr. Put the line back
# and run.

started = time.perf_counter()
try:
    payload = run_async(call_lookup(config, "DF-1001", timeout=20))
except Exception as exc:
    payload = None
    print("client_error", type(exc).__name__, exc)
print("seconds", round(time.perf_counter() - started, 1))
# The server removes its pid file as it exits; leaving async with closed its stdin, so it is gone.
print("server_stopped", not PID_PATH.is_file())
if payload:
    print("protocol_version", payload["protocol_version"])
    print("tools", payload["tools"])
    print("result", payload["result"])
    RUNS_PATH.write_text(json.dumps({"transport": server["transport"], **payload}, indent=2) + "\n", encoding="utf-8")
    print("wrote", RUNS_PATH.relative_to(RUNS_PATH.parents[3]).as_posix())

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
if committed_run:
    RUNS_PATH.write_text(committed_run, encoding="utf-8")
print("restored_client", bool(committed_run))
# A server that is killed instead of exiting (keep_alive left on, then the lab process ends) leaves one behind.
if PID_PATH.is_file():
    PID_PATH.unlink()
    print("cleared_pid_file", True)
print("pid_file_left", PID_PATH.is_file())
