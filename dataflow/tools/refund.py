"""Pretend refunds. A real row on disk, no real money."""

from __future__ import annotations

import json
import os
from pathlib import Path

from langchain.tools import tool

DATAFLOW = Path(__file__).resolve().parents[1]
REFUNDS_PATH = DATAFLOW / "data" / "refunds.jsonl"


def get_refunds_path() -> Path:
    """Path for the refunds ledger. Tests override via env or REFUNDS_PATH."""
    env = os.environ.get("DATAFLOW_REFUNDS_PATH", "").strip()
    if env:
        return Path(env)
    return Path(REFUNDS_PATH)


def read_refunds() -> list[dict]:
    path = get_refunds_path()
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def write_refund(order_id: str, amount: float, reason: str) -> dict:
    """Append one refunded row. Side effect is the jsonl file, not a bank."""
    row = {
        "refunded": True,
        "order_id": order_id,
        "amount": float(amount),
        "reason": reason,
    }
    path = get_refunds_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


@tool
def issue_refund(order_id: str, amount: float, reason: str) -> dict:
    """Issue a pretend refund. Appends one row to refunds.jsonl. No real money."""
    from harness.permissions import apply_write_permission

    apply_write_permission("issue_refund", order_id)
    return write_refund(order_id, amount, reason)


@tool
def decline_refund(order_id: str, reason: str) -> dict:
    """Decline a refund. Typed miss, no disk write."""
    from harness.permissions import apply_write_permission

    apply_write_permission("decline_refund", order_id)
    return {
        "refunded": False,
        "declined": True,
        "order_id": order_id,
        "reason": reason,
    }
