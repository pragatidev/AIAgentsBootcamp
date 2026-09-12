"""Named profile facts with a date, a source, a lifetime, and a forget path."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from langgraph.store.base import BaseStore

PROFILE_KEY = "profile"

LIFETIMES = {
    "contact_channel": timedelta(days=365),
    "mood": timedelta(days=1),
    "plan": timedelta(days=90),
    "note": timedelta(days=30),
}


def profile_namespace(customer_id: str) -> tuple[str, str]:
    return ("customers", str(customer_id))


def put_profile(
    store: BaseStore,
    customer_id: str,
    key: str,
    value: str,
    source: str,
    written_at: datetime | None = None,
) -> dict:
    now = written_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    ns = profile_namespace(customer_id)
    item = store.get(ns, PROFILE_KEY)
    current = dict(item.value) if item is not None else {}
    current[key] = {
        "value": value,
        "written_at": now.isoformat(),
        "source": source,
    }
    store.put(ns, PROFILE_KEY, current)
    return current


def read_profile(
    store: BaseStore,
    customer_id: str,
    now: datetime | None = None,
    lifetimes: dict[str, timedelta] | None = None,
) -> dict[str, Any]:
    """Drop keys past their lifetime before the model sees the profile."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    lives = lifetimes or LIFETIMES
    ns = profile_namespace(customer_id)
    item = store.get(ns, PROFILE_KEY)
    if item is None:
        return {"profile": {}, "dropped": []}
    kept: dict[str, Any] = {}
    dropped: list[str] = []
    for key, rec in dict(item.value or {}).items():
        if not isinstance(rec, dict):
            dropped.append(key)
            continue
        raw = rec.get("written_at") or ""
        try:
            written = datetime.fromisoformat(str(raw))
        except ValueError:
            dropped.append(key)
            continue
        if written.tzinfo is None:
            written = written.replace(tzinfo=timezone.utc)
        life = lives.get(key, timedelta(days=365))
        if now - written > life:
            dropped.append(key)
            continue
        kept[key] = rec
    if dropped:
        store.put(ns, PROFILE_KEY, kept)
    return {"profile": kept, "dropped": dropped}


def forget(store: BaseStore, customer_id: str) -> list[str]:
    """Delete the customer's namespace. Returns the keys that were removed."""
    ns = profile_namespace(customer_id)
    deleted: list[str] = []
    for item in store.search(ns):
        store.delete(item.namespace, item.key)
        deleted.append(item.key)
    return deleted
