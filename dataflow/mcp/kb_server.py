"""The knowledge team's MCP server: DataFlow's retrieve, served over MCP (Lecture 28.9).

One tool, retrieve, which calls dataflow.tools.retrieve.retrieve_passages, the same search the
desk's local retrieve tool runs. An MCP call carries no DataFlow envelope, so every question
searches the customer scope (the wiki and the customer facing pages).

On stdio the server's stdout is the protocol channel: one stray print breaks the next answer.
retrieve.py prints a line when it builds or refreshes an index, so each call sends prints to
stderr while it runs.

Run over stdio: python -m dataflow.mcp.kb_server
"""

from __future__ import annotations

import contextlib
import importlib
import os
import sys

from fastmcp import FastMCP

# The module, not the tool of the same name that dataflow.tools exports. Looked up at call time.
_retrieve = importlib.import_module("dataflow.tools.retrieve")

kb = FastMCP("kb")


@kb.tool(description=_retrieve.RETRIEVE_DESCRIPTION, annotations={"readOnlyHint": True})
def retrieve(question: str, k: int = 3) -> list[dict] | dict:
    with contextlib.redirect_stdout(sys.stderr):
        return _retrieve.retrieve_passages(question, k=k, scope="customer")


if __name__ == "__main__":
    os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")
    kb.run(transport="stdio", show_banner=False)
