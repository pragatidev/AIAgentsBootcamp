"""Order lookup. No model. Data is northstar/data/orders.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

ORDERS_PATH = Path(__file__).resolve().parents[1] / "data" / "orders.json"


def load_orders() -> dict[str, dict]:
    return json.loads(ORDERS_PATH.read_text(encoding="utf-8"))


def lookup_order(ticket: str) -> dict:
    orders = load_orders()
    match = re.search(r"NS-\d+", ticket.upper())
    if not match:
        return {"found": False, "reason": "no order id in the ticket"}
    order_id = match.group(0)
    row = orders.get(order_id)
    if not row:
        return {"found": False, "order_id": order_id, "reason": "unknown order"}
    return {"found": True, "order_id": order_id, **row}
