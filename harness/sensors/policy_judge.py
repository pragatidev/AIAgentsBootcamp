"""Inferential control: one model call against a policy paragraph."""

from __future__ import annotations

import json
from typing import Any

from config import get_chat_model


def _content_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(getattr(block, "text", block)))
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


def _usage_dict(message: Any) -> dict[str, Any]:
    usage = getattr(message, "usage_metadata", None)
    if usage is None:
        meta = getattr(message, "response_metadata", None) or {}
        if isinstance(meta, dict):
            usage = meta.get("usage") or meta.get("token_usage")
    if isinstance(usage, dict):
        return dict(usage)
    if usage is None:
        return {}
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def policy_judge(record, policy_text) -> dict:
    """Ask the model from config whether the record follows the policy.

    Returns verdict plus tokens from usage_metadata. One call.
    """
    chat = get_chat_model()
    message = chat.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You judge one DataFlow refund record against a policy paragraph. "
                    "Reply with PASS or FAIL on the first line, then one sentence."
                ),
            },
            {
                "role": "user",
                "content": (
                    "policy:\n"
                    + str(policy_text)
                    + "\n\nrecord:\n"
                    + json.dumps(record, ensure_ascii=True)
                ),
            },
        ]
    )
    text = _content_text(message).strip()
    usage = _usage_dict(message)
    first = text.splitlines()[0].upper() if text else ""
    if "FAIL" in first and "PASS" not in first.split("FAIL")[0]:
        verdict = "FAIL"
    elif first.startswith("PASS") or " PASS" in (" " + first):
        verdict = "PASS"
    elif "FAIL" in text.upper() and "PASS" not in text.upper().split("FAIL")[0]:
        verdict = "FAIL"
    else:
        verdict = "PASS"
    tokens = usage.get("total_tokens")
    if tokens is None:
        inp = usage.get("input_tokens") or 0
        out = usage.get("output_tokens") or 0
        tokens = int(inp) + int(out)
    return {
        "verdict": verdict,
        "text": text,
        "tokens": tokens,
        "usage": usage,
    }
