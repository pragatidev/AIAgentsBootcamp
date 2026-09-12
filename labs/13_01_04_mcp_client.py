# %% [markdown]
# Call the MCP tool from a stdio client.
#
# When this works, lookup prints with the transport named. The break is
# a streamable HTTP URL nothing serves. The fix is stdio matching the
# script.

# %%
from pathlib import Path
import json
import os
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")

import config
from dataflow.mcp.client import load_config, load_http_config, run_lookup
from dataflow.mcp.server import PID_PATH

run_path = root / "dataflow" / "mcp" / "runs" / "client.json"
committed_run = run_path.read_text(encoding="utf-8") if run_path.is_file() else ""

print("model", config.CHAT_MODEL)
print("python", sys.executable)
print("config_command_was", "python")
cfg = load_config(sys.executable)
print("config_command_now", cfg["mcpServers"]["dataflow"]["command"])
print("transport", cfg["mcpServers"]["dataflow"]["transport"])

payload = run_lookup("DF-1001", cfg=cfg, write=True)
print("result_transport", payload.get("transport"))
print("tools", payload.get("tools"))
print("result", payload.get("result"))
print("wrote", run_path.as_posix())

# %%
print("cell", "break")
print("BREAK: client configured for a streamable HTTP URL that nothing serves")
try:
    run_lookup(
        "DF-1001",
        cfg=load_http_config("http://127.0.0.1:1/mcp"),
        timeout=2,
        write=False,
    )
    print("http_unexpectedly_ok")
except Exception as exc:
    print("http_error", type(exc).__name__)
    print(str(exc)[:400])

# %%
print("cell", "fix")
print("FIX: stdio matches the script and the result prints")
fixed = run_lookup("DF-1001", cfg=load_config(sys.executable), write=True)
print("fix_transport", fixed.get("transport"))
print("fix_result", fixed.get("result"))

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_run:
    run_path.write_text(committed_run, encoding="utf-8")
print("restored_client", bool(committed_run))
if PID_PATH.is_file():
    PID_PATH.unlink()
    print("cleared_pid_file", True)
