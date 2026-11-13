"""The desk loads only the MCP servers the company approved, as they were approved (Lectures 29.7, 29.8).

allowlist.json names each approved server and pins every tool it may offer by a fingerprint: the SHA-256
of the tool's name, description and input schema, which is everything the model will be told about it.
A server that is not listed is refused. A tool whose fingerprint changed (an update rewrote its
description, or a poison was added) is refused until someone approves the new one.

A server's name is its own claim (serverInfo). The pinned fingerprints, and the command or URL the host
was approved to use, are what tie the name to the server you checked.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ALLOWLIST_PATH = Path(__file__).with_name("allowlist.json")


def fingerprint(tool: Any) -> str:
    """SHA-256 of what the model is told about a tool: its name, description and input schema."""
    schema = getattr(tool, "args_schema", None)
    if schema is not None and not isinstance(schema, dict):
        schema = schema.model_json_schema()
    seen = {"name": tool.name, "description": tool.description or "", "input_schema": schema or {}}
    return hashlib.sha256(json.dumps(seen, sort_keys=True).encode("utf-8")).hexdigest()


def server_name(tool: Any) -> str:
    """The server a bound MCP tool came from, as the server names itself."""
    return str(((tool.metadata or {}).get("mcp") or {}).get("server", {}).get("name", ""))


def load_allowlist(path: Path = ALLOWLIST_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_server(name: str, tools: list[Any], allowlist: dict) -> list[str]:
    """Why this server's tools may not load. Empty means every tool is approved as it is now."""
    entry = allowlist["servers"].get(name)
    if entry is None:
        return [f"server {name} is not on the allowlist"]
    refusals = []
    for tool in tools:
        pinned = entry["tools"].get(tool.name)
        if pinned is None:
            refusals.append(f"{name}.{tool.name} was never approved")
        elif pinned != fingerprint(tool):
            refusals.append(f"{name}.{tool.name} changed since it was approved")
    return refusals


def approve(allowlist: dict, name: str, tools: list[Any], note: str = "") -> dict:
    """A new allowlist with this server's tools pinned as they are now. The old one is not changed."""
    servers = {key: dict(value) for key, value in allowlist["servers"].items()}
    servers[name] = {"note": note or servers.get(name, {}).get("note", ""), "tools": {tool.name: fingerprint(tool) for tool in tools}}
    return {**allowlist, "servers": servers}


def approved_servers(allowlist: dict | None = None) -> set[str]:
    """The names of every server on the allowlist."""
    return set((allowlist or load_allowlist())["servers"])
