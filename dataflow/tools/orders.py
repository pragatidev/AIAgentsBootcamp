"""Order lookup. Typed LangChain tool. No model required to look up a row."""

from __future__ import annotations

import json
import re
from pathlib import Path

from langchain.tools import tool

ORDERS_PATH = Path(__file__).resolve().parents[1] / "data" / "orders.json"


def load_orders() -> dict[str, dict]:
    return json.loads(ORDERS_PATH.read_text(encoding="utf-8"))


def lookup_order(ticket: str) -> dict:
    """Look up by DF-#### inside a ticket string. Used by the fixture loop."""
    orders = load_orders()
    match = re.search(r"DF-\d+", ticket.upper())
    if not match:
        return {"found": False, "reason": "no order id in the ticket"}
    order_id = match.group(0)
    row = orders.get(order_id)
    if not row:
        return {"found": False, "order_id": order_id, "reason": "unknown order"}
    return {"found": True, "order_id": order_id, **row}


def lookup_order_by_id(order_id: str) -> dict:
    """Look up one id. A miss is a dict, not a crash."""
    orders = load_orders()
    key = order_id.strip().upper()
    row = orders.get(key)
    if not row:
        return {"found": False, "order_id": key, "reason": "unknown order"}
    return {"found": True, "order_id": key, **row}


@tool
def lookup_order_tool(order_id: str) -> str:
    """Look up a DataFlow order by id like DF-1001. Returns JSON."""
    row = lookup_order_by_id(order_id)
    return json.dumps(row)
