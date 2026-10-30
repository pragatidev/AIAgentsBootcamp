"""Who may call which desk tool, as data. The envelope says who is asking; the model's text never does.

The tenant here is the region (US or EU): the repo has one company, and region is the only field that
splits it. A real multi-tenant desk also splits storage, keys and logs per tenant; this in-memory
directory and the in-memory saver are single-tenant by construction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from techcorp.tools.accounts import _find_user

SHARES_PATH = Path(__file__).resolve().parents[1] / "data" / "shares.json"
SHARES: dict[str, list[str]] = json.loads(SHARES_PATH.read_text(encoding="utf-8"))

# target: whose account the call touches. "caller" is the envelope's user; otherwise the argument named.
RULES: dict[str, dict[str, Any]] = {
    "lookup_user": {"roles": ("employee", "it_agent"), "target": "query"},
    "reset_password": {"roles": ("employee", "it_agent"), "target": "caller"},
    "grant_access": {"roles": ("it_agent",), "target": "user_id", "listed_share": True},
}


def _miss(role: str, tool_name: str, reason: str) -> dict:
    return {"found": False, "reason": reason, "role": role, "tool": tool_name}


def check(tool_name: str, args: dict, ctx: Any) -> dict | None:
    """None when the caller in the envelope may make this call; otherwise a typed miss naming the role, the tool and why."""
    caller = (getattr(ctx, "user_id", None) or "").strip()
    role = getattr(ctx, "role", None) or "employee"
    region = getattr(ctx, "region", None) or "US"
    rule = RULES.get(tool_name)
    if rule is None:
        return _miss(role, tool_name, f"no rule allows {tool_name}")
    if not caller:
        return _miss(role, tool_name, "no acting user in the request envelope")
    if _find_user(caller) is None:
        return _miss(role, tool_name, f"unknown caller {caller}")
    if role not in rule["roles"]:
        return _miss(role, tool_name, f"role {role} may not call {tool_name}")
    target = caller if rule["target"] == "caller" else str(args.get(rule["target"]) or "")
    row = _find_user(target)
    if row is None:
        return None  # the tool answers an unknown id with its own typed miss
    if role == "employee" and row["user_id"].lower() != caller.lower():
        return _miss(role, tool_name, "an employee may act on their own account only")
    if row.get("region") != region:
        return _miss(role, tool_name, f"{row['user_id']} is in region {row.get('region')}; this desk serves {region}")
    if rule.get("listed_share"):
        share = str(args.get("share") or "")
        if share not in SHARES:
            return _miss(role, tool_name, f"share {share} is not on the share list")
        if row.get("department") not in SHARES[share]:
            return _miss(role, tool_name, f"share {share} is for {', '.join(SHARES[share])}")
    return None
