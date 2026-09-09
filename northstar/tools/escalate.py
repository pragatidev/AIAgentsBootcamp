"""Escalate to a human. No model. The gate is a dict, not a chat."""


def escalate_to_human(ticket: str) -> dict:
    return {
        "escalate": True,
        "queue": "support-human",
        "ticket": ticket,
        "reason": "policy does not cover this ticket",
    }
