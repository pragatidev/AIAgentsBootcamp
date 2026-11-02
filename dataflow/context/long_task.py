"""The capstone's long task: sixty turns for one customer, built only from text already on disk.

The 5.2 intro states the 40 dollar rule at turn four; the middle mixes the 5.2 fillers with ticket
texts from dataflow/data/tickets.jsonl that name no other customer and no other customer's order;
the last turn is the 5.2 probe.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from dataflow.context.guard import CUSTOMER_ID_RE
from dataflow.context.rot import CONSTRAINT, FILLERS, PROBE, judge_refund_reply, states_cap

TICKETS_PATH = Path(__file__).resolve().parents[1] / "data" / "tickets.jsonl"
INTRO = [
    "Hi, this is about order DF-1001, the desk lamp.",
    "It arrived unused. I might want a refund later.",
    "Please keep this account on the starter plan.",
    CONSTRAINT,
]


def ticket_texts(customer_id: str = "C-2001") -> list[str]:
    """Ticket texts this customer could have written: their own, or ones that name no order and no customer."""
    texts = []
    for line in TICKETS_PATH.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        text = row["text"]
        if row["customer_id"] == customer_id or not (re.search(r"DF-\d+", text) or CUSTOMER_ID_RE.search(text)):
            texts.append(text)
    return texts


def build_long_task(n: int = 60, customer_id: str = "C-2001") -> list[str]:
    """The intro, then a ticket after every two fillers until n - 1 turns, then the probe."""
    tickets = ticket_texts(customer_id)
    fillers = list(FILLERS)
    middle: list[str] = []
    while len(INTRO) + len(middle) < n - 1:
        if len(middle) % 3 == 2 and tickets:
            middle.append(tickets.pop(0))
        elif fillers:
            middle.append(fillers.pop(0))
        elif tickets:
            middle.append(tickets.pop(0))
        else:
            raise ValueError(f"not enough text on disk for {n} turns")
    return INTRO + middle + [PROBE]


def pass_lines(result: dict, rows: list[dict], limit: int, customer_id: str) -> dict:
    """The capstone's checks, read from the run's result and its window log."""
    last = rows[-1] if rows else {"messages": []}
    others = sorted(
        {cid for row in rows for m in row["messages"] for cid in CUSTOMER_ID_RE.findall(m["text"])} - {customer_id}
    )
    return {
        "turns": len(result["replies"]),
        "calls": len(rows),
        "max_window_tokens": max((row["window_tokens"] for row in rows), default=0),
        "stayed_under": all(row["window_tokens"] <= limit for row in rows),
        "compactions": sum(1 for row in result["token_trace"] if row.get("event") == "compact"),
        "verdict": judge_refund_reply(result["replies"][-1]) if result["replies"] else None,
        "cap_in_last_window": [m["source"] for m in last["messages"] if states_cap(m["text"])],
        "other_customer_ids_in_window": others,
    }
