"""Stdio client for the DataFlow MCP server.

Starts `python -m dataflow.mcp.server` as a subprocess. The python path
is filled in at run time so this file is not tied to one machine.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dataflow.mcp.runtime import run_async

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).with_name("client_config.json")
RUNS_PATH = Path(__file__).resolve().parent / "runs" / "client.json"


def stdio_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Env the stdio subprocess actually sees.

    MCP stdio only inherits a short Windows allowlist. PYTHONPATH and
    DATAFLOW_REFUNDS_PATH must be passed in or the child cannot import
    dataflow and cannot write the temp ledger.
    """
    env: dict[str, str] = {
        "PYTHONPATH": str(ROOT),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "FASTMCP_SHOW_SERVER_BANNER": "false",
    }
    for key in (
        "VIRTUAL_ENV",
        "DATAFLOW_REFUNDS_PATH",
        "OLLAMA_BASE_URL",
        "OLLAMA_CHAT_MODEL",
    ):
        value = os.environ.get(key, "").strip()
        if value:
            env[key] = value
    extra_path = os.environ.get("PYTHONPATH", "").strip()
    if extra_path and extra_path not in env["PYTHONPATH"]:
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + extra_path
    if extra:
        env.update(extra)
    return env


def load_config(python_cmd: str | None = None) -> dict:
    """Read client_config.json and put this interpreter in as the command."""
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    server = cfg["mcpServers"]["dataflow"]
    server["command"] = python_cmd or sys.executable
    server["cwd"] = str(ROOT)
    server["transport"] = "stdio"
    server["env"] = stdio_env()
    return cfg


def load_http_config(url: str = "http://127.0.0.1:1/mcp") -> dict:
    """Plant: streamable HTTP to a URL nothing serves. Lab 13.1.4 only."""
    return {
        "mcpServers": {
            "dataflow": {
                "url": url,
                "transport": "http",
            }
        }
    }


async def _call(cfg: dict, order_id: str, timeout: float) -> dict:
    from fastmcp import Client

    os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")
    client = Client(cfg, timeout=timeout, init_timeout=timeout)
    try:
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            result = await client.call_tool("lookup_order", {"order_id": order_id})
            payload = {
                "transport": str(
                    cfg.get("mcpServers", {}).get("dataflow", {}).get("transport")
                    or "stdio"
                ),
                "tools": names,
                "result": result.data,
            }
            return payload
    finally:
        transport = getattr(client, "transport", None)
        if transport is not None and hasattr(transport, "close"):
            try:
                await transport.close()
            except Exception:
                pass


def run_lookup(
    order_id: str = "DF-1001",
    *,
    cfg: dict | None = None,
    timeout: float = 30,
    write: bool = True,
) -> dict:
    """List tools, call lookup_order, optionally write runs/client.json."""
    config = cfg if cfg is not None else load_config()
    payload = run_async(_call(config, order_id, timeout))
    if write:
        RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RUNS_PATH.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    return payload
