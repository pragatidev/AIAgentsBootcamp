"""Order lookup. Typed LangChain tool. No model required to look up a row."""

from __future__ import annotations

import json
import re
from pathlib import Path

from langchain.tools import tool

ORDERS_PATH = Path(__file__).resolve().parents[1] / "data" / "orders.json"


def load_orders() -> dict[str, dict]:
    return json.loads(ORDERS_PATH.read_text(encoding="utf-8"))


def lookup_order_by_id(order_id: str) -> dict:
    """Look up one id. A miss is a dict, not a crash.

    Accepts a bare id like DF-1001, or a longer string that contains one.
    """
    orders = load_orders()
    raw = (order_id or "").strip()
    match = re.search(r"DF-\d+", raw.upper())
    key = match.group(0) if match else raw.upper()
    if not key:
        return {"found": False, "reason": "no order id in the ticket"}
    row = orders.get(key)
    if not row:
        return {"found": False, "order_id": key, "reason": "unknown order"}
    return {"found": True, "order_id": key, **row}


def lookup_order_from_ticket(ticket: str) -> dict:
    """Look up by DF-#### inside a ticket string. Used by the fixture loop."""
    match = re.search(r"DF-\d+", (ticket or "").upper())
    if not match:
        return {"found": False, "reason": "no order id in the ticket"}
    return lookup_order_by_id(match.group(0))


@tool
def lookup_order(order_id: str) -> dict:
    """Look up a DataFlow order by id like DF-1001. Returns the row or a typed miss."""
    return lookup_order_by_id(order_id)


@tool
def lookup_order_tool(order_id: str) -> str:
    """Look up a DataFlow order by id like DF-1001. Returns JSON."""
    return json.dumps(lookup_order_by_id(order_id))
