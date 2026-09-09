"""S15: structured miss and one retry. Fail closed."""

from __future__ import annotations

import json


def parse_tool_json(raw: str, retries: int = 1) -> dict:
    last_error = ""
    text = raw
    for _ in range(retries + 1):
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("not an object")
            return {"ok": True, "data": data}
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = str(exc)
            text = text[text.find("{") :] if "{" in text else text
    return {"ok": False, "error": last_error, "fail_closed": True}
