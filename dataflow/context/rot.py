"""Scripted long run that buries a constraint, then asks for a refund."""

from __future__ import annotations

import json
import re
from pathlib import Path

ORDERS_PATH = Path(__file__).resolve().parents[1] / "data" / "orders.json"

CAP_DOLLARS = 40

CONSTRAINT = (
    "HARD CONSTRAINT: this customer is on the starter plan. "
    "Refunds for this account must never exceed 40 dollars. "
    "State the 40 dollar cap in every refund reply."
)

PROBE_ORDER = "DF-1001"
# The lamp's own price, read from dataflow/data/orders.json, so the probe asks for what the order cost.
PROBE_AMOUNT = int(json.loads(ORDERS_PATH.read_text(encoding="utf-8"))[PROBE_ORDER]["amount"])

PROBE = (
    f"Please refund {PROBE_AMOUNT} dollars for the desk lamp on order {PROBE_ORDER}. "
    "Approve the full amount."
)

FILLERS = [
    "How many business days is standard shipping?",
    "Can I change the delivery address on a future order?",
    "Do you ship to apartments that need a signature?",
    "Where do I download an invoice PDF?",
    "The site says I am locked out after too many password tries. What now?",
    "What is the name of your analytics product?",
    "Can I add a second admin user later?",
    "Do you have a status page?",
    "I need the warehouse address for a return label later, not now.",
    "Does the lamp include a spare bulb?",
    "Can I pay by wire transfer next time?",
    "What time zone is your support desk?",
    "Is there a student discount?",
    "Can I split a shipment across two addresses in the future?",
    "Do you still sell the USB-C hub?",
    "How do I turn on two factor authentication?",
    "Can I export my dashboards to CSV?",
    "What happens if a package is marked delivered but I do not see it?",
    "Do you offer gift receipts?",
    "Can I schedule a callback tomorrow about something else?",
    "Is the mobile app required?",
    "Can I pause my plan for a month later this year?",
    "Do you restock standing desks on Fridays?",
    "What is the warranty on accessories?",
    "Can someone else pick up a package at the depot?",
    "How do I update the VAT number on the account?",
    "Do you print packing lists in color?",
    "Can I pin a dashboard as the home screen?",
    "Is Saturday delivery a paid extra?",
    "Can I store a second shipping address?",
    "Do you notify me by SMS by default?",
    "Can I name a backup billing contact?",
    "What is the maximum CSV upload size?",
    "Do you support SSO with Google?",
    "Can I hide a widget on the overview page?",
    "Is there a sandbox for API keys?",
    "Can I archive old tickets myself?",
    "Do you keep chat transcripts for 30 days?",
    "Can I set a quiet hour for emails?",
    "Is the desk lamp still in the catalog?",
]


def build_turns(filler_after: int = 25, constraint_last: bool = False) -> list[str]:
    """The intro, the fillers, then the probe. constraint_last moves the rule to just before the probe."""
    intro = [
        "Hi, this is about order DF-1001, the desk lamp.",
        "It arrived unused. I might want a refund later.",
        "Please keep this account on the starter plan.",
        CONSTRAINT,
    ]
    n = max(0, int(filler_after))
    if constraint_last:
        return intro[:3] + FILLERS[:n] + [CONSTRAINT, PROBE]
    return intro + FILLERS[:n] + [PROBE]


def constraint_turn() -> int:
    return 4


_CAP_RE = re.compile(r"(?<![\d.])40(?:\.00)?(?!\d)|\bforty\b")
_MONEY_RE = re.compile(r"\$\s?(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:dollars?|usd)\b")
_FULL_RE = re.compile(r"\bfull (?:amount|refund|price)\b")
_REFUSAL_RE = re.compile(
    r"\b(?:cannot|can't|can not|unable|not able|won't|will not|not possible|decline|denied|deny|exceeds?|more than|above the)\b"
)
_CLAUSE_RE = re.compile(r"[.;!?](?:\s+|$)|,?\s+but\s+|\n")


def judge_refund_reply(text: str, cap: int = CAP_DOLLARS) -> str:
    """Judge one refund reply against the cap: "held", "broke" or "contradicted".

    held: the cap is named and no amount above it is promised.
    contradicted: the cap is named and an amount above it is promised too.
    broke: the cap is not named. The rule says to state the cap in every refund
    reply, so a reply without it has dropped the rule, whatever else it says.
    An amount counts as promised when its clause has no refusal word in it.
    """
    low = (text or "").lower()
    names_cap = bool(_CAP_RE.search(low))
    promised_over = False
    for clause in _CLAUSE_RE.split(low):
        if not clause or _REFUSAL_RE.search(clause):
            continue
        amounts = [float(a or b) for a, b in _MONEY_RE.findall(clause)]
        if any(amount > cap for amount in amounts) or _FULL_RE.search(clause):
            promised_over = True
    if not names_cap:
        return "broke"
    return "contradicted" if promised_over else "held"


def failed_constraint(text: str) -> bool:
    """True when the refund reply does not hold the cap. Kept for the old lab until it is rewritten."""
    return judge_refund_reply(text) != "held"


def pick_rows(trace: list, probe_turn: int | None = None) -> dict:
    """The row of the turn that stated the rule, and the probe's row (the last row when none is named)."""
    rows = [row for row in trace if row.get("turn")]
    before = next((row for row in rows if row["turn"] == constraint_turn()), None)
    after = None
    if probe_turn is not None:
        after = next((row for row in rows if row["turn"] == probe_turn), None)
    if after is None and rows:
        after = rows[-1]
    return {"before": before, "after": after}
