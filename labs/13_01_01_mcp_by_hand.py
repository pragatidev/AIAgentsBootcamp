# %%
"""Lab 28.3: an MCP request by hand.

What we build: nothing new on the desk. You talk to the DataFlow MCP server that ships in the repo with
no MCP library on your side. You type the envelope every request travels in, start the server as a child
process, write four JSON lines to its stdin and read four answers from its stdout.

What you learn: MCP is messages. A request is one JSON-RPC line with a method, its params and an id, and
the answer comes back with the same id. There is no handshake and no session, so every single request
carries two keys in params._meta: the protocol revision it speaks and the client's capabilities.

What will be true on your screen: each line sent and received, raw, then the fields that matter.
server/discover answers supportedVersions ["2026-07-28"] with the server's name and capabilities;
tools/list gives lookup_order and refund with their input and output schemas, in the same order both
times; tools/call on lookup_order for DF-1001 gives content, structuredContent with found true, and
isError false; and the server exits with code 0 when its stdin closes.
"""

# Run this one from the terminal: `python labs/13_01_01_mcp_by_hand.py`.
# no-twin: an MCP stdio client starts the server as a subprocess and needs a real stderr handle, which a Jupyter kernel does not have.

from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from dataflow.mcp.client import ROOT, stdio_env
from dataflow.mcp.server import PID_PATH

PROTOCOL_VERSION = "2026-07-28"


# %%
# TYPE THIS: envelope. The signature and docstring are given; you type the body.
# There is no finished copy in the package: from Lecture 28.7 on, FastMCP's client builds this for you.
def envelope(method: str, params: dict, request_id: int) -> str:
    """One JSON-RPC request as one line: the method, its params, an id, and the two _meta keys every request carries."""
    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {**params, "_meta": meta}}
    return json.dumps(message)


# BREAK: delete the line that sets "io.modelcontextprotocol/protocolVersion" above and run. Nothing in your
# requests says you speak 2026-07-28 now, so the server reads your first line as a client from an older
# revision, one that must open with an initialize handshake: server/discover is -32601 Method not found and
# every later request is -32602 Invalid request parameters. Put the line back, delete the clientCapabilities
# line instead and run: the version routes you to 2026-07-28, and each answer is -32602 naming the missing
# key. Put it back and run.


# %%
# The server is a child process. It reads requests on stdin and writes answers on stdout, one line each.
# stdio_env() adds what the child needs to import dataflow; Lecture 28.7 shows why a client must pass it.
child = subprocess.Popen(
    [sys.executable, "-m", "dataflow.mcp.server"],
    cwd=str(ROOT),
    env={**os.environ, **stdio_env()},
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
    encoding="utf-8",
)


def ask(method: str, params: dict, request_id: int) -> dict:
    line = envelope(method, params, request_id)
    print("SEND", line)
    child.stdin.write(line + "\n")
    child.stdin.flush()
    answer = child.stdout.readline().strip()
    print("RECV", answer)
    reply = json.loads(answer)
    if "error" in reply:
        print(method, "error", reply["error"]["code"], reply["error"]["message"])
    return reply.get("result") or {}


try:
    found = ask("server/discover", {}, 1)
    if found:
        print("discover supportedVersions", found["supportedVersions"])
        print("discover serverInfo", found["_meta"]["io.modelcontextprotocol/serverInfo"])
        print("discover capabilities", sorted(found["capabilities"]))
        print("discover resultType", found["resultType"], "ttlMs", found["ttlMs"], "cacheScope", found["cacheScope"])

    first = ask("tools/list", {}, 2)
    second = ask("tools/list", {}, 3)
    if first:
        names = [tool["name"] for tool in first["tools"]]
        print("tools_first", names)
        print("tools_second", [tool["name"] for tool in second["tools"]])
        print("tools_same_order", names == [tool["name"] for tool in second["tools"]])
        lookup = next(tool for tool in first["tools"] if tool["name"] == "lookup_order")
        print("lookup_order inputSchema", json.dumps(lookup["inputSchema"]))
        print("lookup_order outputSchema", json.dumps(lookup.get("outputSchema")))
        print("lookup_order annotations", json.dumps(lookup.get("annotations")))

    called = ask("tools/call", {"name": "lookup_order", "arguments": {"order_id": "DF-1001"}}, 4)
    if called:
        print("call content", called["content"][0]["text"])
        print("call structuredContent found", called["structuredContent"]["found"])
        print("call isError", called["isError"])
finally:
    # Closing stdin is how a stdio client says goodbye; the server reads end of input and exits by itself.
    child.stdin.close()
    print("server_exit_code", child.wait(timeout=15))
    if PID_PATH.is_file():
        PID_PATH.unlink()
    print("pid_file_left", PID_PATH.is_file())
