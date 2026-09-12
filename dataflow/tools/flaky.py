"""Flaky carrier API for the DataFlow desk.

The world is flaky here, not the model. A module counter makes the
first two calls time out and the third return a real order row.
"""

from __future__ import annotations

from langchain.tools import tool

from dataflow.tools.orders import lookup_order_by_id

__all__ = [
    "CarrierTimeout",
    "call_count",
    "fetch_carrier_status",
    "reset_flaky",
    "set_always_fail",
]


class CarrierTimeout(Exception):
    """The carrier HTTP call timed out. The world is flaky here, not the model."""


_CALLS = 0
_ALWAYS_FAIL = False


def reset_flaky() -> None:
    """Reset the attempt counter and clear always-fail mode."""
    global _CALLS, _ALWAYS_FAIL
    _CALLS = 0
    _ALWAYS_FAIL = False


def set_always_fail(value: bool = True) -> None:
    """Make every carrier call raise CarrierTimeout. The world stays down."""
    global _ALWAYS_FAIL
    _ALWAYS_FAIL = bool(value)


def call_count() -> int:
    return int(_CALLS)


@tool
def fetch_carrier_status(order_id: str) -> dict:
    """Fetch carrier status for a DataFlow order id like DF-1002.

    The first two calls raise CarrierTimeout. The third returns status
    and item from orders.json. The world is flaky here, not the model.
    """
    global _CALLS
    _CALLS += 1
    if _ALWAYS_FAIL or _CALLS <= 2:
        raise CarrierTimeout(f"carrier timeout on attempt {_CALLS} for {order_id}")
    row = lookup_order_by_id(order_id)
    if not row.get("found"):
        return row
    return {
        "found": True,
        "order_id": row.get("order_id"),
        "status": row.get("status"),
        "item": row.get("item"),
    }
