"""Escalate to a human. No model. The gate is a dict, not a chat."""

from langchain.tools import tool


def escalate_to_human(ticket: str) -> dict:
    return {
        "escalate": True,
        "queue": "support-human",
        "ticket": ticket,
        "reason": "policy does not cover this ticket",
    }


@tool
def escalate(reason: str) -> dict:
    """Park a ticket for a human. No side effects. Returns a ticket-parked dict."""
    return {
        "parked": True,
        "status": "ticket-parked",
        "queue": "support-human",
        "reason": reason,
    }
