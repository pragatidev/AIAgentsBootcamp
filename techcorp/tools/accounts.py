"""TechCorp account tools. Typed misses. Pretend passwords only."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain.tools import ToolRuntime, tool

# Passwords are pretend. Nothing is written to a real directory or mail
# system. The only side effects are an in-memory user dict and an
# appended line in techcorp/data/audit.jsonl (gitignored).

USERS_PATH = Path(__file__).resolve().parents[1] / "data" / "users.json"
AUDIT_PATH = Path(__file__).resolve().parents[1] / "data" / "audit.jsonl"

# Keys that never reach an audit line. The employee gets the temporary password in the
# tool result; the audit file, which a whole team can read, never carries it.
SECRET_KEYS = frozenset({"temporary_password"})

_USERS: dict[str, dict[str, Any]] | None = None


def _load_users() -> dict[str, dict[str, Any]]:
    raw = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    users: dict[str, dict[str, Any]] = {}
    for key, row in raw.items():
        copied = dict(row)
        copied["user_id"] = copied.get("user_id") or key
        copied["groups"] = list(copied.get("groups") or [])
        users[str(copied["user_id"])] = copied
    return users


def get_users() -> dict[str, dict[str, Any]]:
    """In-memory employee directory. Reloaded from disk only when empty."""
    global _USERS
    if _USERS is None:
        _USERS = _load_users()
    return _USERS


def reload_users() -> dict[str, dict[str, Any]]:
    """Reload the directory from disk. Tests use this to undo grants."""
    global _USERS
    _USERS = _load_users()
    return _USERS


def _context_user_id(runtime: Any) -> str | None:
    if runtime is None:
        return None
    ctx = getattr(runtime, "context", None)
    if ctx is None:
        return None
    uid = getattr(ctx, "user_id", None)
    if uid is None and isinstance(ctx, dict):
        uid = ctx.get("user_id")
    if uid is None:
        return None
    text = str(uid).strip()
    return text or None


def acting_user(runtime: Any, requested: str | None = None) -> dict[str, Any]:
    """Decide whose account a write tool acts on. Only the request envelope names the caller.

    The id the model typed (requested) never chooses the account; it is kept only to say
    whether it disagreed with the envelope. An empty envelope is a typed miss.
    """
    envelope = _context_user_id(runtime)
    asked = (requested or "").strip() or None
    if envelope is None:
        return {"ok": False, "reason": "no acting user in the request envelope"}
    mismatch = asked is not None and asked.lower() != envelope.lower()
    return {"ok": True, "user_id": envelope, "requested": asked, "mismatch": mismatch}


def _find_user(query: str) -> dict[str, Any] | None:
    needle = (query or "").strip()
    if not needle:
        return None
    users = get_users()
    lower = needle.lower()
    for user_id, row in users.items():
        if user_id.lower() == lower:
            return row
        name = str(row.get("name") or "")
        if name.lower() == lower:
            return row
    return None


def _public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "found": True,
        "user_id": row["user_id"],
        "name": row.get("name"),
        "email": row.get("email"),
        "department": row.get("department"),
        "vpn_enabled": row.get("vpn_enabled"),
        "groups": list(row.get("groups") or []),
    }


def _temporary_password() -> str:
    """Ten random hex characters. Pretend, but nobody can work it out from the employee id."""
    return secrets.token_hex(5)


def _context_value(runtime: Any, key: str) -> Any:
    ctx = getattr(runtime, "context", None) if runtime is not None else None
    if ctx is None:
        return None
    if isinstance(ctx, dict):
        return ctx.get(key)
    return getattr(ctx, key, None)


def reset_outcome(acting: str) -> dict[str, Any]:
    """The miss shape, found False and a reason, for an empty or unknown id; the hit shape for a known one. Never invent a user."""
    if not acting:
        return {"found": False, "reason": "no user id"}
    row = _find_user(acting)
    if not row:
        return {"found": False, "reason": f"unknown user {acting}"}
    return {
        "found": True,
        "user_id": row["user_id"],
        "temporary_password": _temporary_password(),
        "expires_in_hours": 24,
    }


def _audit(event: dict[str, Any], runtime: Any = None) -> None:
    payload = {key: value for key, value in event.items() if key not in SECRET_KEYS}
    for key in ("ticket_id", "request_id"):
        value = _context_value(runtime, key)
        if value:
            payload[key] = value
    payload["at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=True) + "\n"
    with AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line)


def dummy_runtime(user_id: str | None = None) -> Any:
    """A ToolRuntime-like object for calling reset_password.func in labs and tests."""

    class _Ctx:
        def __init__(self, uid: str | None) -> None:
            self.user_id = uid

    class _Rt:
        def __init__(self, uid: str | None) -> None:
            self.context = _Ctx(uid)

    return _Rt(user_id)


@tool
def lookup_user(query: str) -> dict:
    """Look up a TechCorp employee by user id (E-4101) or by name. Returns the record or a typed miss. Use this before you reset a password."""
    row = _find_user(query)
    if not row:
        return {"found": False, "reason": f"unknown user {query}"}
    return _public_user(row)


@tool
def reset_password(user_id: str, runtime: ToolRuntime[Any]) -> dict:
    """Reset an employee's password and return a pretend temporary password. The employee in the request envelope is the one reset, whatever user_id says; with no id in the envelope the reset is a miss. Never invent a user. Look up the user before you reset. Passwords are pretend."""
    who = acting_user(runtime, user_id)
    if not who["ok"]:
        return {"found": False, "reason": who["reason"]}
    result = reset_outcome(who["user_id"])
    if not result["found"]:
        return result
    event = {
        "action": "reset_password",
        "user_id": result["user_id"],
        "requested_user_id": user_id,
    }
    if who["mismatch"]:
        event["mismatch"] = True
        result["requested_user_id_ignored"] = who["requested"]
    _audit(event, runtime)
    return result


@tool
def grant_access(user_id: str, share: str) -> dict:
    """Grant an employee access to a named share by adding it to their groups. Returns the new group list or a typed miss."""
    row = _find_user(user_id)
    if not row:
        return {"found": False, "reason": f"unknown user {user_id}"}
    name = (share or "").strip()
    if not name:
        return {"found": False, "reason": "no share name"}
    groups = list(row.get("groups") or [])
    if name not in groups:
        groups.append(name)
        row["groups"] = groups
    result = {
        "found": True,
        "user_id": row["user_id"],
        "share": name,
        "groups": list(groups),
    }
    _audit(
        {
            "action": "grant_access",
            "user_id": row["user_id"],
            "share": name,
            "groups": list(groups),
        }
    )
    return result
