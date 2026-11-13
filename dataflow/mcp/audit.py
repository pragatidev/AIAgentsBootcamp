"""An audit line for every MCP tool call (Lecture 29.9).

A FastMCP middleware: on_call_tool runs around every tool call the server receives and appends one JSON
line to a log file: when, who (the token's subject over HTTP, local when there is no token), which tool,
the arguments with free-text fields redacted, the outcome, how long it took, and the W3C traceparent
from the request's _meta when the desk sent one, so a security team can join the call to the desk's
trace. It records who and what, never the credential: the headers it keeps are FastMCP's safe set,
which leaves out authorization and cookie.

FastMCP also ships StructuredLoggingMiddleware for general server logs; this file is the narrower record
an auditor asks for.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp.server.dependencies import get_access_token, get_http_headers
from fastmcp.server.middleware import Middleware

# Arguments a person types in their own words: kept out of the log, since they can carry anything.
REDACT = frozenset({"reason"})


def request_meta(context: Any) -> dict:
    """The request's _meta (protocol keys, a traceparent if the client sent one), or an empty dict."""
    request = getattr(context.fastmcp_context, "request_context", None) if context.fastmcp_context else None
    return dict(getattr(request, "meta", None) or {})


class AuditLog(Middleware):
    """Append one JSON line per tool call to path."""

    def __init__(self, path: str | Path, redact: frozenset[str] = REDACT):
        self.path = Path(path)
        self.redact = redact

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


def read_audit(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
