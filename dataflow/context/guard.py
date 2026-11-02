"""What must never enter the window: instruction lines in retrieved text, secrets, other customers' data.

A pattern list only catches shapes it has seen. What holds is the box plus a desk with no write tool;
Section 31 goes further, with the allowlist at the tool port.
"""

from __future__ import annotations

import re

from dataflow.context.box_text import box
from dataflow.context.redact import redact

# Taken from the two plants on disk: dataflow/wiki/security.md line 7 and
# dataflow/guardrails/fixtures/escalate.md line 6.
INSTRUCTION_PATTERNS = ("agent instruction:", "ignore the customer", "required tool call")
CUSTOMER_ID_RE = re.compile(r"\bC-\d{4}\b")


def strip_instructions(text: str) -> tuple[str, list[str]]:
    """Drop every line that looks like an instruction to the model. Returns the kept text and the dropped lines."""
    kept, dropped = [], []
    for line in (text or "").splitlines():
        if any(p in line.lower() for p in INSTRUCTION_PATTERNS):
            dropped.append(line.strip())
        else:
            kept.append(line)
    return "\n".join(kept), dropped


def guard_read(name: str, text: str) -> tuple[str, list[str]]:
    """Strip instruction lines, mask secrets and emails, then box the rest with its source."""
    clean, dropped = strip_instructions(text)
    return box(name, redact(clean)), dropped


def customer_ids_in(messages: list) -> set[str]:
    """Every customer id that appears anywhere in a message list."""
    found: set[str] = set()
    for m in messages:
        found.update(CUSTOMER_ID_RE.findall(str(m.get("content") or "")))
    return found


def other_customer_ids(messages: list, customer_id: str) -> list[str]:
    """Customer ids in the messages that are not this customer's, sorted."""
    return sorted(customer_ids_in(messages) - {customer_id})
