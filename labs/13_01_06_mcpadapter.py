# %% [markdown]
# Bind MCP tools with MCPAdapter.
#
# When this works, the bound names print, the desk answers where order
# DF-1002 is, the retired adapters import raises ImportError, and the
# langchain.mcp path is the one that bound the tools.

# %%
from pathlib import Path
import os
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")

from langchain_core.messages import HumanMessage

import config
from dataflow.mcp.bind import bind_mcp_tools, bound_names, build_desk, close_mcp
from dataflow.mcp.client import load_config
from dataflow.mcp.server import PID_PATH

print("model", config.CHAT_MODEL)
print("import", "from langchain.mcp import MCPAdapter")

cfg = load_config(sys.executable)
try:
    tools = bind_mcp_tools(cfg)
    print("bound_names", bound_names(tools))
    desk = build_desk(model=config.get_chat_model(), tools=tools)
    out = desk.invoke(
        {"messages": [HumanMessage(content="Where is order DF-1002?")]}
    )
    messages = list(out.get("messages") or [])
    reply = ""
    for message in reversed(messages):
        calls = list(getattr(message, "tool_calls", None) or [])
        if calls:
            continue
        text = str(getattr(message, "content", "") or "")
        if text:
            reply = text
            break
    print("reply", reply)
finally:
    close_mcp()
    if PID_PATH.is_file():
        PID_PATH.unlink()

# %%
print("cell", "break")
print("BREAK: import langchain_mcp_adapters MultiServerMCPClient")
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: F401
    print("retired_import_unexpectedly_ok")
except Exception as exc:
    print("retired_import_error", type(exc).__name__)
    print(exc)

# %%
print("cell", "fix")
print("FIX: langchain.mcp MCPAdapter is the maintained path")
from langchain.mcp import MCPAdapter

print("adapter_class", MCPAdapter.__name__)
print("adapter_module", MCPAdapter.__module__)
