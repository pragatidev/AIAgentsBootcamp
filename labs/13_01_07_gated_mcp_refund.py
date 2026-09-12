# %% [markdown]
# Gate an MCP refund tool with interrupt.
#
# When this works, the park payload prints, deny on thread A writes
# nothing, approve on thread B writes one row, a graph with no
# checkpointer cannot resume, and the server pid is still there after
# both resumes.

# %%
from pathlib import Path
import os
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")

import config
from dataflow.mcp.bind import bind_mcp_tools, close_mcp
from dataflow.mcp.client import load_config
from dataflow.mcp.gated import build_gated_mcp, resume_gated
from dataflow.mcp.server import PID_PATH
from dataflow.tools.refund import read_refunds
from langgraph.types import Command

print("model", config.CHAT_MODEL)


def temp_refunds() -> str:
    handle = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
    handle.close()
    os.environ["DATAFLOW_REFUNDS_PATH"] = handle.name
    return handle.name


def read_server_pid() -> int | None:
    if not PID_PATH.is_file():
        return None
    raw = PID_PATH.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    return int(raw)


def pid_alive(pid: int) -> bool:
    # os.kill(pid, 0) is the Unix probe. On Windows signal 0 is not a
    # valid parameter (WinError 87), so OpenProcess is the check.
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


payload_in = {
    "order_id": "DF-1001",
    "amount": 49.0,
    "reason": "unused lamp",
}

refunds_path = temp_refunds()
print("refunds_path", refunds_path)
cfg = load_config(sys.executable)
try:
    tools = bind_mcp_tools(cfg)
    pid_before = read_server_pid()
    print("server_pid_before", pid_before)
    print("server_alive_before", pid_alive(pid_before) if pid_before else False)

    print("cell", "park_then_deny")
    graph = build_gated_mcp(model=config.get_chat_model(), tools=tools)
    deny_cfg = {"configurable": {"thread_id": "mcp-thread-A"}}
    print("thread_A", deny_cfg["configurable"]["thread_id"])
    graph.invoke(dict(payload_in), deny_cfg)
    state = graph.get_state(deny_cfg)
    print("parked", bool(state.interrupts))
    print("payload", state.interrupts[0].value if state.interrupts else None)
    resume_gated(graph, deny_cfg, False)
    deny_rows = read_refunds()
    print("deny_rows", deny_rows)
    print("deny_count", len(deny_rows))

    print("cell", "fresh_thread_approve")
    ok_cfg = {"configurable": {"thread_id": "mcp-thread-B"}}
    print("thread_B", ok_cfg["configurable"]["thread_id"])
    graph.invoke(dict(payload_in), ok_cfg)
    resume_gated(graph, ok_cfg, True)
    ok_rows = read_refunds()
    print("approve_rows", ok_rows)
    print("approve_count", len(ok_rows))

    pid_after = read_server_pid()
    print("server_pid_after", pid_after)
    print("server_alive_after", pid_alive(pid_after) if pid_after else False)
    print("pid_unchanged", pid_before == pid_after)

    print("cell", "break")
    print("BREAK: a graph with no checkpointer cannot resume")
    bare = build_gated_mcp(
        model=config.get_chat_model(),
        tools=tools,
        checkpointer=False,
    )
    parked = bare.invoke(dict(payload_in))
    print("no_checkpointer_park", bool(parked.get("__interrupt__")))
    try:
        bare.invoke(Command(resume={"approve": False}))
        print("resume_without_checkpointer_unexpectedly_ok")
    except Exception as exc:
        print("resume_without_checkpointer_error", type(exc).__name__)
        print(str(exc)[:400])
    print(
        "note: a killed MCP session is the same failure: the park has nowhere "
        "to resume because the connection died with the process"
    )

    print("cell", "fix")
    print("FIX: the checkpointer holds the thread and the server subprocess is still up")
    print("fix_thread_A", deny_cfg["configurable"]["thread_id"])
    print("fix_thread_B", ok_cfg["configurable"]["thread_id"])
    print("fix_pid", pid_after)
finally:
    close_mcp()
    if PID_PATH.is_file():
        PID_PATH.unlink()
