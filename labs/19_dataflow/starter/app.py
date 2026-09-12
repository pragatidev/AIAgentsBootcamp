"""FastAPI door for the DataFlow capstone starter. Health plus POST /run."""

from __future__ import annotations

import os
import uuid
from typing import Any

from dataflow.graphs.rag_graph import REFUSE_TEMPLATE

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
except ImportError:
    FastAPI = None  # type: ignore[misc, assignment]
    Request = None  # type: ignore[misc, assignment]
    JSONResponse = None  # type: ignore[misc, assignment]


def health() -> dict:
    return {"ok": True, "service": "dataflow"}


def use_fixture_model() -> bool:
    return os.environ.get("DATAFLOW_UI_MODEL", "").strip().lower() == "fixture"


def fixture_reply(question: str) -> dict[str, Any]:
    q = (question or "").lower()
    if "refund" in q:
        return {
            "answer": "Refund parked for a reviewer.",
            "refuse": False,
            "parked": True,
            "route": "refund",
            "thread_id": "fixture-park",
            "payload": {
                "action": "refund",
                "order_id": "DF-1001",
                "amount": 49.0,
            },
        }
    unknown = ("coffee", "gym", "warranty", "lounge", "beans")
    if any(word in q for word in unknown):
        return {
            "answer": REFUSE_TEMPLATE.format(q=question),
            "refuse": True,
            "parked": False,
            "route": "refuse",
            "thread_id": "fixture-refuse",
        }
    if "df-100" in q or "order" in q:
        return {
            "answer": "Order DF-1002 is in_transit. Item: standing desk.",
            "refuse": False,
            "parked": False,
            "route": "lookup",
            "thread_id": "fixture-lookup",
        }
    return {
        "answer": "The customer return window is 30 days from delivery.",
        "refuse": False,
        "parked": False,
        "route": "retrieve",
        "thread_id": "fixture-policy",
    }


def real_reply(question: str) -> dict[str, Any]:
    from config import get_chat_model

    from graph import run_ticket

    out = run_ticket(question, model=get_chat_model(), thread_id="door-" + uuid.uuid4().hex)
    reply = str(out.get("reply") or out.get("answer") or "")
    parked = bool(out.get("parked"))
    refused = "I do not have that in the knowledge base" in reply
    route = str(out.get("route") or "")
    if parked:
        route = "refund"
    elif refused:
        route = "refuse"
    return {
        "answer": reply,
        "refuse": refused,
        "parked": parked,
        "route": route,
        "thread_id": "door",
        "payload": out.get("payload"),
    }


def desk_reply(question: str) -> dict[str, Any]:
    if use_fixture_model():
        return fixture_reply(question)
    return real_reply(question)


def _build_app():
    if FastAPI is None:
        return None
    app = FastAPI()

    @app.get("/health")
    def health_route() -> dict:
        return health()

    @app.post("/run")
    async def run_route(request: Request) -> Any:
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"detail": "ticket is required"}, status_code=422)
        if not isinstance(payload, dict):
            return JSONResponse({"detail": "ticket is required"}, status_code=422)
        ticket = str(payload.get("ticket") or "").strip()
        if not ticket:
            return JSONResponse({"detail": "ticket is required"}, status_code=422)
        result = desk_reply(ticket)
        return {
            "thread_id": str(result.get("thread_id") or "desk"),
            "route": str(result.get("route") or ""),
            "reply": str(result.get("answer") or ""),
            "parked": bool(result.get("parked")),
            "payload": result.get("payload"),
        }

    return app


app = _build_app()
