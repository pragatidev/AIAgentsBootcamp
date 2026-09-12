"""Python export of the Langflow DataFlow ticket flow.

As first exported, TOOL_SCHEMA is empty, so the model cannot call lookup.
Pass --fill-schema to load the lookup schema from dataflow.tools.orders.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import config

TICKET = (
    "Hi, I want to return order DF-1001. The desk lamp is unused. "
    "Can I get a refund?"
)

# Plant: Langflow left the exported tool schema empty.
TOOL_SCHEMA: dict = {}

ORDERS_PATH = ROOT / "dataflow" / "data" / "orders.json"
POLICY_PATH = ROOT / "dataflow" / "wiki" / "return_policy.md"

LOOKUP_PARAMETERS = {
    "type": "object",
    "properties": {
        "order_id": {
            "type": "string",
            "description": "Order id like DF-1001",
        }
    },
    "required": ["order_id"],
}


def lookup_order_by_id(order_id: str) -> dict:
    orders = json.loads(ORDERS_PATH.read_text(encoding="utf-8"))
    raw = (order_id or "").strip()
    match = re.search(r"DF-\d+", raw.upper())
    key = match.group(0) if match else raw.upper()
    if not key:
        return {"found": False, "reason": "no order id in the ticket"}
    row = orders.get(key)
    if not row:
        return {"found": False, "order_id": key, "reason": "unknown order"}
    return {"found": True, "order_id": key, **row}


def policy_text() -> str:
    return POLICY_PATH.read_text(encoding="utf-8")


def policy_line() -> str:
    for line in policy_text().splitlines():
        if "unused" in line.lower() and "30" in line:
            return line.strip()
    return policy_text().splitlines()[2].strip()


def ollama_chat(messages: list, tools: list | None = None) -> dict:
    base = config.OLLAMA_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    url = base + "/api/chat"
    body: dict = {
        "model": config.CHAT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0},
    }
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _tool_calls(message: dict) -> list:
    raw = message.get("tool_calls") or []
    if raw:
        return raw
    return []


def run(fill_schema: bool = False) -> dict:
    if fill_schema:
        parameters = LOOKUP_PARAMETERS
        description = (
            "Look up a DataFlow order by id like DF-1001. "
            "Returns the row or a typed miss."
        )
    else:
        parameters = TOOL_SCHEMA
        description = ""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_order",
                "description": description,
                "parameters": parameters,
            },
        }
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "You are the DataFlow support desk. "
                "When the user names an order id, call lookup_order. "
                "Do not invent an order row. After the tool result, "
                "write one short customer reply."
            ),
        },
        {"role": "user", "content": TICKET},
    ]
    first = ollama_chat(messages, tools=tools)
    msg = first.get("message") or {}
    calls = _tool_calls(msg)
    lookup_called = False
    order_row = None
    proposed = [str((c.get("function") or {}).get("name") or "") for c in calls]
    schema_has_order_id = bool((parameters or {}).get("properties", {}).get("order_id"))
    for call in calls:
        fn = call.get("function") or {}
        if fn.get("name") != "lookup_order":
            continue
        if not schema_has_order_id:
            # Empty export schema: no order_id property, so lookup cannot run.
            continue
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        order_id = str(args.get("order_id") or "")
        if not order_id:
            continue
        lookup_called = True
        order_row = lookup_order_by_id(order_id)
        messages.append(msg)
        messages.append(
            {
                "role": "tool",
                "content": json.dumps(order_row),
            }
        )
        messages.append(
            {
                "role": "user",
                "content": "Return policy:\n" + policy_text(),
            }
        )
        second = ollama_chat(messages)
        msg = second.get("message") or {}
        break
    reply = str(msg.get("content") or "")
    out = {
        "fill_schema": fill_schema,
        "model": config.CHAT_MODEL,
        "base_url": config.OLLAMA_BASE_URL,
        "tool_schema": parameters,
        "proposed_tools": proposed,
        "schema_has_order_id": schema_has_order_id,
        "lookup_called": lookup_called,
        "order_row": order_row,
        "policy_line": policy_line() if lookup_called else None,
        "reply": reply,
    }
    return out


if __name__ == "__main__":
    fill = "--fill-schema" in sys.argv
    payload = run(fill_schema=fill)
    print(json.dumps(payload, indent=2, ensure_ascii=True))
