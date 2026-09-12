"""Write permissions live on the harness, not in a prompt."""

from __future__ import annotations

from contextvars import ContextVar

ALLOWED_REFUND_ACTORS = {"reviewer-1", "reviewer-2", "desk-lead"}

_enabled: ContextVar[bool] = ContextVar("harness_perm_on", default=False)
_actor: ContextVar[str] = ContextVar("harness_actor", default="anon")


class PermissionDenied(Exception):
    """Typed refusal. Names the actor and the tool."""

    def __init__(self, actor_id: str, tool_name: str, order_id: str) -> None:
        self.actor_id = actor_id
        self.tool_name = tool_name
        self.order_id = order_id
        super().__init__(
            "PermissionDenied: actor "
            + str(actor_id)
            + " may not call "
            + str(tool_name)
            + " on "
            + str(order_id)
        )


def set_permission_context(*, enabled: bool, actor_id: str) -> None:
    _enabled.set(bool(enabled))
    _actor.set(str(actor_id or "anon"))


def current_actor() -> str:
    return _actor.get()


def checks_enabled() -> bool:
    return bool(_enabled.get())


def check_write_permission(tool_name, actor_id, order_id) -> None:
    if tool_name not in {"issue_refund", "decline_refund"}:
        return
    if actor_id not in ALLOWED_REFUND_ACTORS:
        raise PermissionDenied(str(actor_id), str(tool_name), str(order_id))


def apply_write_permission(tool_name, order_id) -> None:
    """Called at the top of a mutating tool. No-op when checks are off."""
    if not _enabled.get():
        return
    check_write_permission(tool_name, _actor.get(), order_id)
