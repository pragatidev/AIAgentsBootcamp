"""HTTP door for the thin DataFlow chat page and POST /run.

health() stays importable with no extra packages. FastAPI is optional at
import time so clone-contract tests keep passing if the extra deps are
missing. S30 fills the page. S43 adds POST /run, the checkpointer, and
Pydantic models. S44 adds the x-api-key header and the 429 cap. S45
adds request_id on the tracer and the response.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from dataflow.graphs.rag_graph import REFUSE_TEMPLATE
from dataflow.graphs.v1_triage import DeskContext
from dataflow.ops.tracer import (
    LocalTraceHandler,
    current_request_id,
    log_actor,
    set_request_id,
)

ROOT = Path(__file__).resolve().parents[2]


def health() -> dict:
    return {"ok": True, "service": "dataflow"}


PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>DataFlow desk</title>
  <style>
    body { font-family: sans-serif; max-width: 40rem; margin: 2rem auto; }
    textarea { width: 100%; height: 6rem; }
    #answer { min-height: 3rem; white-space: pre-wrap; margin-top: 1rem; }
    .citation, .refuse, .parked { margin-top: 0.5rem; }
  </style>
</head>
<body>
  <h1>DataFlow desk</h1>
  <textarea id="q" placeholder="Ask the desk"></textarea>
  <p><button id="send">Send</button></p>
  <div id="answer"></div>
  <div id="extra"></div>
  <script>
    async function send() {
      const q = document.getElementById('q').value;
      const answer = document.getElementById('answer');
      const extra = document.getElementById('extra');
      answer.textContent = '';
      extra.innerHTML = '';
      const res = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: q})
      });
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buf += dec.decode(value, {stream: true});
        const parts = buf.split('\\n\\n');
        buf = parts.pop();
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data:')) continue;
          const payload = JSON.parse(line.slice(5).trim());
          if (payload.text) answer.textContent += payload.text;
          if (payload.citation) {
            const el = document.createElement('div');
            el.className = 'citation';
            el.textContent = payload.citation;
            extra.appendChild(el);
          }
          if (payload.refuse) {
            const el = document.createElement('div');
            el.className = 'refuse';
            el.textContent = 'REFUSE';
            extra.appendChild(el);
          }
          if (payload.parked) {
            const el = document.createElement('div');
            el.className = 'parked';
            el.textContent = 'parked';
            extra.appendChild(el);
          }
        }
      }
    }
    document.getElementById('send').addEventListener('click', send);
  </script>
</body>
</html>
"""


class RunRequest(BaseModel):
    """Ticket on the door. thread_id is optional and must stay short."""

    ticket: str = ""
    thread_id: str | None = None
    resume: Any | None = None

    @model_validator(mode="after")
    def ticket_or_thread(self) -> "RunRequest":
        ticket = (self.ticket or "").strip()
        thread_id = (self.thread_id or "").strip()
        if not ticket and not thread_id:
            raise ValueError("ticket is required")
        if thread_id and len(thread_id) > 255:
            raise ValueError("thread_id must be under 255 characters")
        return self


class RunResponse(BaseModel):
    thread_id: str
    route: str = ""
    reply: str = ""
    parked: bool = False
    payload: dict[str, Any] | None = None
    actor: str = ""


def use_fixture_model() -> bool:
    return os.environ.get("DATAFLOW_UI_MODEL", "").strip().lower() == "fixture"


def fixture_reply(question: str) -> dict[str, Any]:
    """Scripted page facts for Playwright. No Ollama."""
    q = (question or "").lower()
    if "refund" in q:
        return {
            "answer": "Refund parked for a reviewer.",
            "citation": None,
            "refuse": False,
            "parked": True,
            "interrupt": {
                "action": "refund",
                "order_id": "DF-1001",
                "amount": 89.0,
                "reason": "fixture park",
            },
        }
    unknown = (
        "coffee",
        "gym",
        "warranty",
        "lounge",
        "island",
        "cattle",
        "beans",
    )
    if any(word in q for word in unknown):
        return {
            "answer": REFUSE_TEMPLATE.format(q=question),
            "citation": None,
            "refuse": True,
            "parked": False,
        }
    return {
        "answer": "The customer return window is 30 days from delivery.",
        "citation": "dataflow/wiki/return_policy.md",
        "refuse": False,
        "parked": False,
    }


def real_reply(question: str) -> dict[str, Any]:
    """Run the desk. Refund-shaped tickets park through v4 interrupt."""
    from config import get_chat_model

    text = question or ""
    if "refund" in text.lower():
        from langgraph.checkpoint.memory import InMemorySaver

        from dataflow.graphs.v4_hitl import build_v4_hitl

        saver = InMemorySaver()
        graph = build_v4_hitl(model=get_chat_model(), checkpointer=saver)
        cfg = {"configurable": {"thread_id": "ui-" + uuid.uuid4().hex}}
        graph.invoke({"ticket": text}, cfg)
        state = graph.get_state(cfg)
        if state.interrupts:
            payload = state.interrupts[0].value
            return {
                "answer": "Waiting for a reviewer to confirm the refund.",
                "citation": None,
                "refuse": False,
                "parked": True,
                "interrupt": payload if isinstance(payload, dict) else {"value": payload},
            }
        values = state.values or {}
        return {
            "answer": str(values.get("reply") or ""),
            "citation": None,
            "refuse": False,
            "parked": False,
        }

    from dataflow.graphs.rag_graph import build_rag_graph

    graph = build_rag_graph(model=get_chat_model(), scope="all")
    state = graph.invoke({"question": text})
    reply = str(state.get("reply") or state.get("answer") or "")
    sources = list(state.get("sources") or [])
    citation = None
    if sources:
        first = sources[0]
        if isinstance(first, dict):
            citation = str(first.get("source") or "")
        else:
            citation = str(first)
    refused = "I do not have that in the knowledge base" in reply
    return {
        "answer": reply,
        "citation": citation or None,
        "refuse": refused,
        "parked": False,
    }


def desk_reply(question: str) -> dict[str, Any]:
    if use_fixture_model():
        return fixture_reply(question)
    return real_reply(question)


def _sse(payload: dict[str, Any]) -> str:
    return "data: " + json.dumps(payload) + "\n\n"


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def http_log_path() -> Path:
    raw = os.environ.get("DATAFLOW_HTTP_LOG", "").strip()
    if raw:
        return Path(raw)
    return ROOT / "ops" / "tracing" / "runs" / "http.jsonl"


def parse_api_keys() -> dict[str, str]:
    """Map x-api-key value to an owner. Comma separated. key:owner or key."""
    raw = os.environ.get("DATAFLOW_API_KEYS", "").strip()
    owners: dict[str, str] = {}
    if not raw:
        return owners
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" in item:
            key, owner = item.split(":", 1)
            owners[key.strip()] = owner.strip()
        else:
            owners[item] = ""
    return owners


_saver: Any = None
_sqlite_conn: Any = None
_pg_pool: Any = None
_graphs: dict[str, Any] = {}
_thread_meta: dict[str, Any] = {}
_fixture_parked: dict[str, Any] = {}
_rate_buckets: dict[tuple[str, str], list[float]] = {}


def _sqlite_path() -> Path:
    raw = os.environ.get("DATAFLOW_SQLITE_PATH", "").strip()
    if raw:
        return Path(raw)
    return ROOT / "dataflow" / "data" / "serve_checkpoints.sqlite"


def _meta_path() -> Path | None:
    kind = os.environ.get("DATAFLOW_CHECKPOINTER", "memory").strip().lower()
    if kind != "sqlite":
        return None
    return Path(str(_sqlite_path()) + ".meta.json")


def _save_meta() -> None:
    path = _meta_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "threads": _thread_meta,
        "fixture_parked": _fixture_parked,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _load_meta() -> None:
    global _thread_meta, _fixture_parked
    path = _meta_path()
    if path is None or not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    threads = payload.get("threads")
    if isinstance(threads, dict):
        _thread_meta.update(threads)
    parked = payload.get("fixture_parked")
    if isinstance(parked, dict):
        _fixture_parked.update(parked)


def make_checkpointer() -> Any:
    """Pick the saver from DATAFLOW_CHECKPOINTER.

    postgres uses PostgresSaver with DATAFLOW_PG_URL and runs setup once.
    sqlite uses a file. Default is in-memory.
    """
    global _sqlite_conn, _pg_pool
    kind = os.environ.get("DATAFLOW_CHECKPOINTER", "memory").strip().lower()
    if kind == "postgres":
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        from langgraph.checkpoint.postgres import PostgresSaver

        url = (
            os.environ.get("DATAFLOW_PG_URL", "").strip()
            or os.environ.get("POSTGRES_URL", "").strip()
        )
        if not url:
            raise RuntimeError("DATAFLOW_PG_URL is empty")
        pool = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=4,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        pool.open(wait=True, timeout=5)
        _pg_pool = pool
        saver = PostgresSaver(pool)
        saver.setup()
        return saver
    if kind == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver

        path = _sqlite_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        _sqlite_conn = conn
        saver = SqliteSaver(conn)
        saver.setup()
        return saver
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()


def get_saver() -> Any:
    global _saver
    if _saver is None:
        _saver = make_checkpointer()
        _load_meta()
    return _saver


def get_graph(kind: str) -> Any:
    from config import get_chat_model

    if kind not in _graphs:
        saver = get_saver()
        if use_fixture_model():
            # Fixture runs do not compile a model graph. A placeholder
            # sqlite saver still exists so a restart can reload parks.
            _graphs[kind] = None
            return None
        model = get_chat_model()
        if kind == "refund":
            from dataflow.graphs.v4_hitl import build_v4_hitl

            _graphs[kind] = build_v4_hitl(model=model, checkpointer=saver)
        else:
            from dataflow.graphs.rag_graph import build_rag_graph

            _graphs[kind] = build_rag_graph(
                model=model, checkpointer=saver, scope="all"
            )
    return _graphs[kind]


def reset_runtime() -> None:
    """Drop compiled graphs and reopen the saver. Labs use this after a kill."""
    global _saver, _sqlite_conn, _pg_pool, _graphs, _thread_meta
    global _fixture_parked, _rate_buckets
    if _sqlite_conn is not None:
        try:
            _sqlite_conn.close()
        except Exception:
            pass
    if _pg_pool is not None:
        try:
            _pg_pool.close()
        except Exception:
            pass
    _saver = None
    _sqlite_conn = None
    _pg_pool = None
    _graphs = {}
    _thread_meta = {}
    _fixture_parked = {}
    _rate_buckets = {}
    _load_meta()


def reset_rate_buckets() -> None:
    _rate_buckets.clear()


def check_rate_limit(key: str, route: str) -> float | None:
    """Per-key, per-route window. Returns Retry-After seconds when limited."""
    if _flag("DATAFLOW_RATE_LIMIT_OFF"):
        return None
    try:
        cap = int(os.environ.get("DATAFLOW_RATE_LIMIT", "0") or "0")
    except ValueError:
        cap = 0
    if cap <= 0:
        return None
    try:
        window = float(os.environ.get("DATAFLOW_RATE_WINDOW_SEC", "60") or "60")
    except ValueError:
        window = 60.0
    now = time.time()
    bucket = _rate_buckets.setdefault((key, route), [])
    keep = [t for t in bucket if now - t < window]
    bucket[:] = keep
    if len(bucket) >= cap:
        oldest = min(bucket) if bucket else now
        retry = max(1.0, window - (now - oldest))
        return retry
    bucket.append(now)
    return None


def _looks_like_refund(ticket: str) -> bool:
    return "refund" in (ticket or "").lower()


def _new_thread_id() -> str:
    return "df-" + uuid.uuid4().hex


def _tokens_from_trace(path: Path) -> dict[str, int]:
    totals = {"input": 0, "output": 0, "total": 0}
    if not path.is_file():
        return totals
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        tokens = row.get("tokens")
        if not isinstance(tokens, dict):
            continue
        totals["input"] += int(tokens.get("input") or 0)
        totals["output"] += int(tokens.get("output") or 0)
        totals["total"] += int(tokens.get("total") or 0)
    return totals


def _append_http_log(row: dict[str, Any]) -> None:
    path = http_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")


def _interrupt_payload(state: Any) -> dict[str, Any] | None:
    interrupts = list(getattr(state, "interrupts", None) or [])
    if not interrupts:
        return None
    value = interrupts[0].value
    if isinstance(value, dict):
        return value
    return {"value": value}


def _skip_interrupt_write(ticket: str, actor: str) -> dict[str, Any]:
    from dataflow.tools.orders import lookup_order_from_ticket
    from dataflow.tools.refund import write_refund

    order = lookup_order_from_ticket(ticket)
    order_id = str(order.get("order_id") or "DF-1001")
    amount = float(order.get("amount") or 0)
    row = write_refund(order_id, amount, "skip interrupt plant", actor=actor)
    return {
        "thread_id": _new_thread_id(),
        "route": "refund",
        "reply": "Refund issued for order " + order_id + " without parking.",
        "parked": False,
        "payload": row,
        "actor": actor,
    }


def _fixture_run(
    ticket: str,
    thread_id: str,
    actor: str,
    resume: Any,
) -> dict[str, Any]:
    if thread_id in _fixture_parked and resume is None:
        row = dict(_fixture_parked[thread_id])
        row["actor"] = actor or row.get("actor") or ""
        return row
    if _flag("DATAFLOW_SKIP_INTERRUPT") and _looks_like_refund(ticket):
        return _skip_interrupt_write(ticket, actor)
    result = fixture_reply(ticket)
    route = "refund" if result.get("parked") else (
        "refuse" if result.get("refuse") else "lookup"
    )
    if "return window" in (ticket or "").lower() or result.get("citation"):
        if not result.get("parked") and not result.get("refuse"):
            route = "policy"
    payload = result.get("interrupt") if result.get("parked") else None
    body = {
        "thread_id": thread_id,
        "route": route,
        "reply": str(result.get("answer") or ""),
        "parked": bool(result.get("parked")),
        "payload": payload if isinstance(payload, dict) else None,
        "actor": actor,
    }
    if body["parked"]:
        _fixture_parked[thread_id] = dict(body)
        _thread_meta[thread_id] = {"kind": "refund", "parked": True}
        log_actor(actor or "anon", "park")
        _save_meta()
    else:
        _thread_meta[thread_id] = {"kind": "rag", "parked": False}
        _save_meta()
    return body


def _real_run(
    ticket: str,
    thread_id: str,
    actor: str,
    resume: Any,
    request_id: str,
) -> dict[str, Any]:
    from config import CHAT_MODEL, get_chat_model

    if _flag("DATAFLOW_SKIP_INTERRUPT") and _looks_like_refund(ticket):
        return _skip_interrupt_write(ticket, actor)

    kind = "refund" if _looks_like_refund(ticket) else "rag"
    if not ticket and thread_id in _thread_meta:
        kind = str(_thread_meta[thread_id].get("kind") or kind)
    graph = get_graph(kind)
    cfg: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    handler = LocalTraceHandler(run_name="http-run", run_id=request_id or None)
    cfg["callbacks"] = [handler]
    from dataflow.ops import tracer as tracer_mod

    tracer_mod.last_trace_path = handler.path
    ctx = DeskContext(
        model=get_chat_model(),
        user_id=actor,
        actor_id=actor,
        customer_id=actor or "anon",
    )
    handler.open_run("http-run")
    error: BaseException | None = None
    try:
        if resume is not None:
            from langgraph.types import Command

            graph.invoke(
                Command(resume=resume),
                cfg,
                context=ctx,
                durability="sync",
            )
        elif ticket:
            payload: dict[str, Any]
            if kind == "refund":
                payload = {"ticket": ticket}
            else:
                payload = {"question": ticket, "ticket": ticket}
            graph.invoke(payload, cfg, context=ctx, durability="sync")
        state = graph.get_state(cfg)
    except BaseException as exc:
        error = exc
        raise
    finally:
        handler.close_run(error)

    values = (state.values or {}) if state is not None else {}
    parked_payload = _interrupt_payload(state)
    parked = parked_payload is not None
    reply = str(values.get("reply") or values.get("answer") or "")
    if parked and not reply:
        reply = "Waiting for a reviewer to confirm the refund."
    route = str(values.get("route") or kind)
    if parked:
        route = "refund"
        log_actor(actor or "anon", "park")
    _thread_meta[thread_id] = {"kind": kind, "parked": parked}
    _save_meta()
    tokens = _tokens_from_trace(handler.path)
    return {
        "thread_id": thread_id,
        "route": route,
        "reply": reply,
        "parked": parked,
        "payload": parked_payload,
        "actor": actor,
        "tokens": tokens,
        "trace_path": str(handler.path),
        "model": CHAT_MODEL,
    }


def run_ticket(
    ticket: str,
    thread_id: str | None,
    actor: str,
    resume: Any = None,
    request_id: str = "",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    get_saver()
    tid = (thread_id or "").strip() or _new_thread_id()
    if len(tid) > 255:
        tid = tid[:255]
    actor = actor or "anon"
    if use_fixture_model():
        body = _fixture_run(ticket, tid, actor, resume)
        tokens = {"input": 0, "output": 0, "total": 0}
        trace_path = ""
        from config import CHAT_MODEL

        model = CHAT_MODEL
    else:
        body = _real_run(ticket, tid, actor, resume, request_id)
        tokens = body.pop("tokens", {"input": 0, "output": 0, "total": 0})
        trace_path = str(body.pop("trace_path", "") or "")
        model = str(body.pop("model", "") or "")
    ms = round((time.perf_counter() - t0) * 1000, 2)
    rid = request_id or current_request_id()
    _append_http_log(
        {
            "request_id": rid,
            "thread_id": body["thread_id"],
            "route": body.get("route") or "",
            "parked": bool(body.get("parked")),
            "actor": actor,
            "tokens": tokens,
            "ms": ms,
            "model": model,
            "ticket_chars": len(ticket or ""),
            "trace_path": trace_path,
        }
    )
    body["ms"] = ms
    body["request_id"] = rid
    return body


def _enforce_actor() -> bool:
    return bool(parse_api_keys()) and not _flag("DATAFLOW_SKIP_API_KEY")


def _actor_for(x_api_key: str | None, x_actor_id: str | None) -> str:
    keys = parse_api_keys()
    owner = ""
    if x_api_key and x_api_key in keys:
        owner = keys.get(x_api_key) or ""
    actor = (x_actor_id or "").strip() or owner or "anon"
    return actor


def _api_key_ok(x_api_key: str | None) -> bool:
    if _flag("DATAFLOW_SKIP_API_KEY"):
        return True
    keys = parse_api_keys()
    if not keys:
        return True
    if not x_api_key:
        return False
    return x_api_key in keys


try:
    from fastapi import FastAPI, Header, Request
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

    app = FastAPI(title="DataFlow desk")

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        rid = uuid.uuid4().hex
        request.state.request_id = rid
        if _flag("DATAFLOW_DROP_REQUEST_ID"):
            set_request_id("")
        else:
            set_request_id(rid)
        try:
            response = await call_next(request)
        finally:
            set_request_id("")
        response.headers["x-request-id"] = rid
        return response

    @app.get("/health")
    def health_route() -> Any:
        if _flag("DATAFLOW_BROKEN_HEALTH"):
            return JSONResponse(
                {"ok": False, "service": "dataflow"},
                status_code=500,
            )
        return health()

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(PAGE_HTML)

    @app.post("/chat")
    async def chat(request: Request) -> StreamingResponse:
        body = await request.json()
        question = str(body.get("question") or body.get("q") or "")

        async def generate():
            import asyncio

            result = await asyncio.to_thread(desk_reply, question)
            text = str(result.get("answer") or "")
            step = 8 if use_fixture_model() else 24
            delay = 0.12 if use_fixture_model() else 0.02
            for i in range(0, max(len(text), 1), step):
                chunk = text[i : i + step]
                if chunk:
                    yield _sse({"text": chunk})
                    await asyncio.sleep(delay)
            if result.get("citation"):
                yield _sse({"citation": result["citation"]})
            if result.get("refuse"):
                yield _sse({"refuse": "REFUSE"})
            if result.get("parked"):
                yield _sse(
                    {
                        "parked": True,
                        "payload": result.get("interrupt") or {},
                    }
                )
            yield _sse({"done": True})

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/run")
    def run_route(
        body: RunRequest,
        request: Request,
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
        x_actor_id: str | None = Header(default=None, alias="x-actor-id"),
    ) -> Any:
        if not _api_key_ok(x_api_key):
            return JSONResponse(
                {"detail": "missing or invalid x-api-key"},
                status_code=401,
            )
        key_name = x_api_key or "anon"
        retry_after = check_rate_limit(key_name, "/run")
        if retry_after is not None:
            seconds = int(retry_after) if retry_after >= 1 else 1
            return JSONResponse(
                {"detail": "rate limit", "retry_after": seconds},
                status_code=429,
                headers={"Retry-After": str(seconds)},
            )
        actor = _actor_for(x_api_key, x_actor_id)
        ticket = (body.ticket or "").strip()
        if _enforce_actor() and _looks_like_refund(ticket):
            from dataflow.guardrails.allowlist import ToolNotAllowed, check_tool_call
            from harness.permissions import set_permission_context

            set_permission_context(enabled=True, actor_id=actor)
            try:
                check_tool_call("issue_refund", actor)
            except ToolNotAllowed as exc:
                rid = getattr(request.state, "request_id", "") or ""
                _append_http_log(
                    {
                        "request_id": rid,
                        "thread_id": body.thread_id or "",
                        "route": "refund",
                        "parked": False,
                        "actor": actor,
                        "tokens": {"input": 0, "output": 0, "total": 0},
                        "ms": 0,
                        "model": "",
                        "ticket_chars": len(ticket),
                        "trace_path": "",
                        "tool_refused": True,
                    }
                )
                return RunResponse(
                    thread_id=body.thread_id or _new_thread_id(),
                    route="refund",
                    reply=str(exc),
                    parked=False,
                    payload={
                        "error": "ToolNotAllowed",
                        "actor": exc.actor_id,
                        "tool": exc.tool_name,
                    },
                    actor=actor,
                )
        rid = getattr(request.state, "request_id", "") or current_request_id()
        result = run_ticket(
            ticket,
            body.thread_id,
            actor,
            resume=body.resume,
            request_id=rid,
        )
        return RunResponse(
            thread_id=str(result.get("thread_id") or ""),
            route=str(result.get("route") or ""),
            reply=str(result.get("reply") or ""),
            parked=bool(result.get("parked")),
            payload=result.get("payload") if isinstance(result.get("payload"), dict) else None,
            actor=str(result.get("actor") or actor),
        )

except ImportError:
    app = None
