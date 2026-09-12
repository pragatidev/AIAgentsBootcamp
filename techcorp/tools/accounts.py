"""TechCorp account tools. Typed misses. Pretend passwords only."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain.tools import ToolRuntime, tool

# Passwords are pretend. Nothing is written to a real directory or mail
# system. The only side effects are an in-memory user dict and an
# appended line in techcorp/data/audit.jsonl (gitignored).

USERS_PATH = Path(__file__).resolve().parents[1] / "data" / "users.json"
AUDIT_PATH = Path(__file__).resolve().parents[1] / "data" / "audit.jsonl"

_reset_counts: dict[str, int] = {}
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


def _temporary_password(user_id: str) -> str:
    n = _reset_counts.get(user_id, 0) + 1
    _reset_counts[user_id] = n
    digest = hashlib.sha256(f"{user_id}:{n}".encode("utf-8")).hexdigest()
    return digest[:10]


def _audit(event: dict[str, Any]) -> None:
    payload = dict(event)
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
def reset_password(user_id: str, runtime: ToolRuntime) -> dict:
    """Reset an employee's password and return a pretend temporary password. The runtime context user_id wins over this argument when the context carries one. Never invent a user. Look up the user before you reset. Passwords are pretend."""
    acting = _context_user_id(runtime) or (user_id or "").strip()
    if not acting:
        return {"found": False, "reason": "unknown user "}
    row = _find_user(acting)
    if not row:
        return {"found": False, "reason": f"unknown user {acting}"}
    token = _temporary_password(acting)
    result = {
        "found": True,
        "user_id": acting,
        "temporary_password": token,
        "expires_in_hours": 24,
    }
    _audit(
        {
            "action": "reset_password",
            "user_id": acting,
            "requested_user_id": user_id,
            "temporary_password": token,
        }
    )
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
