"""Refund sensor: diff the ledger before and after a write."""

from __future__ import annotations


def _count_for_order(rows: list[dict], order_id: str) -> int:
    n = 0
    for row in rows or []:
        if row.get("order_id") == order_id and row.get("refunded"):
            n += 1
    return n


def refund_diff(before_rows, after_rows, order_id) -> dict:
    """Compare refund rows for one order. Verdict is PASS or FAIL.

    The FAIL message is written for the model to read on the next turn.
    """
    before_n = _count_for_order(before_rows, order_id)
    after_n = _count_for_order(after_rows, order_id)
    if after_n >= 2:
        return {
            "verdict": "FAIL",
            "message": (
                "FAIL: order "
                + str(order_id)
                + " now has "
                + str(after_n)
                + " refund rows. Do not issue another refund. "
                "Decline with the reason already refunded, or stop."
            ),
            "before": before_n,
            "after": after_n,
            "order_id": order_id,
        }
    return {
        "verdict": "PASS",
        "message": (
            "PASS: "
            + str(after_n)
            + " refund row for "
            + str(order_id)
            + "."
        ),
        "before": before_n,
        "after": after_n,
        "order_id": order_id,
    }
