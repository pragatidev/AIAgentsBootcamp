"""The TechCorp desk behind a door: an HTTP service with identity from the API key only.

Run it with: uvicorn --factory techcorp.serve:create_app
Keys come from TECHCORP_API_KEYS as key:user_id:role, comma separated. The caller is whoever owns the key;
no field in a request body and no header the caller writes can name someone else. The approver of a
parked write is the owner of the key that sends the decision. FastAPI is imported inside create_app, so
importing techcorp never needs it. Parked runs live in an in-memory saver; Section 43 puts the
checkpointer on a database.
"""

from __future__ import annotations

import os
from typing import Any, Literal
from uuid import uuid4

from langchain.agents.middleware import ToolCallLimitMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk, reply_text, run_ticket, write_gate
from techcorp.agent.middleware import ApproverRequired, PermissionGate, RunAudit, envelope_prompt
from techcorp.tools.accounts import _find_user


class Ticket(BaseModel):
    """A ticket as the door takes it. There is no identity field: the caller is the key's owner."""

    ticket_id: str
    text: str


class Decision(BaseModel):
    thread_id: str
    decision: Literal["approve", "reject"]
    message: str | None = None


def parse_keys(text: str) -> dict[str, dict[str, str]]:
    """TECHCORP_API_KEYS as key:user_id:role, comma separated, into {key: {"user_id", "role"}}."""
    keys: dict[str, dict[str, str]] = {}
    for item in (text or "").split(","):
        parts = [part.strip() for part in item.split(":")]
        if len(parts) == 3 and all(parts):
            keys[parts[0]] = {"user_id": parts[1], "role": parts[2]}
    return keys


def caller_for(api_key: str | None, keys: dict) -> dict | None:
    """The caller is the key's owner, looked up in the directory for their region; None when the key is unknown."""
    owner = keys.get((api_key or "").strip())
    if owner is None:
        return None
    row = _find_user(owner["user_id"])
    if row is None:
        return None
    return {"user_id": row["user_id"], "role": owner["role"], "region": row["region"]}


def door_middleware() -> list:
    """The door's rules around the loop: tell the model who is asking, park every write, check the rules, need a
    named approver, audit the run, cap it."""
    return [envelope_prompt, write_gate(), PermissionGate(), ApproverRequired(), RunAudit(), ToolCallLimitMiddleware(run_limit=6)]


def _answer(thread_id: str, request_id: str, state: dict) -> dict[str, Any]:
    parked = state["__interrupt__"][0].value["action_requests"] if state.get("__interrupt__") else []
    return {
        "thread_id": thread_id,
        "request_id": request_id,
        "parked": bool(parked),
        "action_requests": [{"name": r["name"], "args": r["args"], "description": r.get("description")} for r in parked],
        "reply": "" if parked else reply_text(state),
    }


def create_app(model=None, keys: dict | None = None, identify=caller_for):
    """Build the FastAPI app. The desk and its model are built on the first ticket, never at import."""
    from fastapi import FastAPI, Header, HTTPException

    table = keys if keys is not None else parse_keys(os.environ.get("TECHCORP_API_KEYS", ""))
    held: dict[str, Any] = {"desk": None, "threads": {}}

    def desk():
        if held["desk"] is None:
            import config

            chat = model if model is not None else config.get_chat_model(reasoning=False)  # thinking off: the reset ticket hit the 4096-token cap
            held["desk"] = build_techcorp_desk(model=chat, middleware=door_middleware(), checkpointer=InMemorySaver())
        return held["desk"]

    app = FastAPI(title="TechCorp IT desk")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/ticket")
    def ticket(body: Ticket, x_api_key: str | None = Header(default=None)) -> dict:
        caller = identify(x_api_key, table)
        if caller is None:
            raise HTTPException(status_code=401, detail="unknown or missing x-api-key")
        thread_id, request_id = f"{body.ticket_id}-{uuid4().hex[:8]}", uuid4().hex
        envelope = {**caller, "ticket_id": body.ticket_id, "request_id": request_id}
        held["threads"][thread_id] = envelope
        state = run_ticket(desk(), f"Ticket {body.ticket_id}: {body.text}", thread_id=thread_id, **envelope)
        return _answer(thread_id, request_id, state)

    @app.post("/resume")
    def resume(body: Decision, x_api_key: str | None = Header(default=None)) -> dict:
        approver = identify(x_api_key, table)
        if approver is None:
            raise HTTPException(status_code=401, detail="unknown or missing x-api-key")
        if approver["role"] != "it_agent":
            raise HTTPException(status_code=403, detail="only an it_agent may decide a parked write")
        envelope = held["threads"].get(body.thread_id)
        if envelope is None:
            raise HTTPException(status_code=404, detail="no such ticket thread")
        run_config = {"configurable": {"thread_id": body.thread_id}}
        interrupts = desk().get_state(run_config).interrupts
        if not interrupts:
            raise HTTPException(status_code=409, detail="nothing is parked on this thread")
        decision: dict[str, Any] = {"type": body.decision}
        if body.decision == "reject" and body.message:
            decision["message"] = body.message
        count = len(interrupts[0].value["action_requests"])
        context = DeskContext(**envelope, approver=approver["user_id"])
        state = desk().invoke(Command(resume={"decisions": [decision] * count}), config=run_config, context=context)
        return _answer(body.thread_id, envelope["request_id"], state)

    return app
