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

# Lecture 17.2 (LG-R5): the bad-input case. The carrier reads the order id before anything else, so an id it
# cannot read fails the same way on every call: a retry sends the same id again.
import re  # noqa: E402

ORDER_ID_SHAPE = re.compile(r"DF-\d{4}")


class CarrierRejected(ValueError):
    """The carrier refused the order id. Bad input, not a flaky world: asking again cannot fix it."""


@tool
def fetch_carrier_status_checked(order_id: str) -> dict:
    """fetch_carrier_status with the carrier's own id check first.

    An id that is not DF- and four digits raises CarrierRejected (a ValueError) on every call. A good id goes
    on to the flaky carrier: two timeouts, then the order row.
    """
    global _CALLS
    if not ORDER_ID_SHAPE.fullmatch(order_id or ""):
        _CALLS += 1
        raise CarrierRejected(f"carrier rejects order id {order_id!r}: not DF- and four digits")
    return fetch_carrier_status.invoke({"order_id": order_id})
