"""S10.4 Keep the last N messages so the desk does not explode. No model."""

from __future__ import annotations


def trim_messages(messages: list[str], keep: int = 4) -> list[str]:
    if keep < 1:
        return []
    return messages[-keep:]
