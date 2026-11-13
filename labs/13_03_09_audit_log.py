# %%
"""Lab 29.9: log every MCP call.

What we build: the audit trail. You type the body of a FastMCP middleware hook, on_call_tool, which runs
around every tool call the server receives and writes one JSON line: the time, the caller (the token's
subject over HTTP, local when there is no token), the tool, the arguments with free-text fields redacted,
the outcome, the duration, and the traceparent the desk sent in the request's _meta. Then the two clerks
from lab 29.4 make calls, and you read the log.

What you learn: an audit line records who did what and when, never the credential. A security team joins
an MCP call to the desk's trace through the traceparent, the W3C trace header the specification carries
in _meta. Free text, like a refund's reason, can carry anything a customer said, so it stays out. The
headers you keep come from FastMCP's get_http_headers(), which leaves out authorization and cookie unless
you ask for everything, and asking for everything is how a bearer token ends up in a log file.

What will be true on your screen: the versions; one log line per call: the read-only clerk's lookup with
its traceparent, its refused refund, the refund clerk's refund with the reason redacted, and a call with
no token logged as local; then that no token and no reason text appear anywhere in the file.
"""

from pathlib import Path
from importlib.metadata import version
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from fastmcp import Client
from fastmcp.server.dependencies import get_access_token, get_http_headers
from fastmcp.server.middleware import Middleware

from dataflow.mcp.audit import REDACT, read_audit, request_meta
from dataflow.mcp.auth import ISSUER, build_auth, mint, stand_in_keys
from dataflow.mcp.http import TOOL_SCOPES, build_http_server, free_port, start_http, url_for
from dataflow.mcp.runtime import run_async

print("mcp", version("mcp"), "fastmcp", version("fastmcp"))

# Temp files for the refund ledger and the audit log, so the run leaves the repo clean.
ledger = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
ledger.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = ledger.name
audit_file = tempfile.NamedTemporaryFile(prefix="mcp-audit-", suffix=".jsonl", delete=False)
audit_file.close()
log_path = Path(audit_file.name)


# %%
class LabAudit(Middleware):
    """Append one JSON line per tool call to path."""

    def __init__(self, path: Path, redact: frozenset = REDACT):
        self.path = path
        self.redact = redact

    # TYPE THIS: on_call_tool. The signature is given; you type the body.
    # Its finished copy is AuditLog.on_call_tool in dataflow/mcp/audit.py.
    async def on_call_tool(self, context, call_next):
        started = time.perf_counter()
        token = get_access_token()
        call = context.message
        row = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "caller": token.claims.get("sub") if token else "local",
            "tool": call.name,
            "args": {k: "[redacted]" if k in self.redact else v for k, v in (call.arguments or {}).items()},
            "traceparent": request_meta(context).get("traceparent"),
            "headers": get_http_headers(),
        }
        try:
            result = await call_next(context)
            row["outcome"] = "error" if getattr(result, "is_error", False) else "ok"
            return result
        except Exception as exc:
            row["outcome"] = f"refused: {type(exc).__name__}"
            raise
        finally:
            row["ms"] = round((time.perf_counter() - started) * 1000, 1)
            with self.path.open("a", encoding="utf-8") as log:
                log.write(json.dumps(row) + "\n")


# BREAK: "log the whole request". Change get_http_headers() above to get_http_headers(include_all=True)
# and run. Every line now carries the authorization header, so each clerk's bearer token sits in the log
# file, and token_in_log prints True. Put it back and run.


# %%
# The orders server over HTTP with the token check (29.3), the scopes (29.4) and your audit middleware.
keys = stand_in_keys()
port = free_port()
url = url_for(port)
auth = build_auth(keys.public_key, ISSUER, url, f"http://127.0.0.1:{port}")
url, stop = start_http(build_http_server(auth=auth, scopes=TOOL_SCOPES, middleware=[LabAudit(log_path)]), port)
TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
REASON = "customer says the lamp flickers, she called twice"
tokens = {
    "read_only_clerk": mint(keys, audience=url, scopes=["orders:read"], subject="read_only_clerk"),
    "refund_clerk": mint(keys, audience=url, scopes=["orders:read", "orders:refund"], subject="refund_clerk"),
}


async def calls() -> None:
    async with Client(url, auth=tokens["read_only_clerk"]) as client:
        await client.call_tool("lookup_order", {"order_id": "DF-1001"}, meta={"traceparent": TRACEPARENT})
        try:
            await client.call_tool("refund", {"order_id": "DF-1001", "amount": 49.0, "reason": REASON})
        except Exception as exc:
            print("read_only_clerk refund", type(exc).__name__, exc)
    async with Client(url, auth=tokens["refund_clerk"]) as client:
        result = await client.call_tool("refund", {"order_id": "DF-1001", "amount": 49.0, "reason": REASON})
        print("refund_clerk refund", json.dumps(result.data))
    # The same server in process, the way a stdio client reaches it: no token, so the caller is local.
    async with Client(build_http_server(middleware=[LabAudit(log_path)])) as client:
        await client.call_tool("lookup_order", {"order_id": "DF-1002"})


run_async(calls())
print("server_stopped", stop())

# %%
rows = read_audit(log_path)
print("log_lines", len(rows))
for row in rows:
    print("audit", json.dumps(row))
text = log_path.read_text(encoding="utf-8")
print("token_in_log", any(token in text for token in tokens.values()))
print("reason_in_log", REASON in text)
