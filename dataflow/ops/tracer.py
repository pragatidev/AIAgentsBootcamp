"""Local tracer for the DataFlow desk.

Records model-call and tool-call spans as jsonl. Never writes graph state.
Works with no LangSmith key. LANGSMITH_TRACING plus LANGSMITH_API_KEY let
the hosted tracer run on its own; this module does not invent a hosted URL.
"""

from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, TypedDict
from uuid import UUID, uuid4

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from dataflow.tools.flaky import fetch_carrier_status

__all__ = [
    "LocalTraceHandler",
    "TRACES_DIR",
    "build_failing_carrier_graph",
    "last_trace_path",
    "render_waterfall",
    "trace",
    "traced_invoke",
]

DATAFLOW = Path(__file__).resolve().parents[1]
TRACES_DIR = DATAFLOW / "data" / "traces"

last_trace_path: Path | None = None
last_actor_line: str | None = None


def log_actor(user_id: str, step: str, run_id: str | None = None) -> str:
    """Print and record actor=<user_id> step=<node name> run=<run id>."""
    global last_actor_line
    rid = run_id or uuid4().hex
    line = "actor=" + str(user_id) + " step=" + str(step) + " run=" + str(rid)
    last_actor_line = line
    print(line, flush=True)
    handler_path = last_trace_path
    if handler_path is not None:
        span = {
            "id": rid,
            "parent_id": None,
            "name": "actor",
            "kind": "actor",
            "status": "ok",
            "actor": str(user_id),
            "step": str(step),
            "run": str(rid),
        }
        with Path(handler_path).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(span, ensure_ascii=True) + "\n")
    return line


def _ensure_traces_dir() -> Path:
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    return TRACES_DIR


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def _sid(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def _summarize(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=True, default=str)
        except TypeError:
            text = str(value)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _content_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(p for p in parts if p)
    if content is None:
        return ""
    return str(content)


def _messages_summary(messages: Any) -> str:
    rows: list[str] = []
    batches = messages if isinstance(messages, list) else [messages]
    for batch in batches:
        items = batch if isinstance(batch, list) else [batch]
        for item in items:
            if isinstance(item, dict):
                rows.append(str(item.get("content") or item))
            else:
                rows.append(_content_text(item))
    return _summarize(" | ".join(r for r in rows if r))


def _tokens_from_usage(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    if not isinstance(usage, dict):
        usage = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
        }
    inp = usage.get("input_tokens")
    if inp is None:
        inp = usage.get("prompt_tokens")
    out = usage.get("output_tokens")
    if out is None:
        out = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if total is None and (inp is not None or out is not None):
        total = int(inp or 0) + int(out or 0)
    if inp is None and out is None and total is None:
        return None
    return {
        "input": int(inp or 0),
        "output": int(out or 0),
        "total": int(total or 0),
    }


def _tokens_from_response(response: Any) -> dict[str, int] | None:
    llm_output = getattr(response, "llm_output", None)
    if isinstance(llm_output, dict):
        found = _tokens_from_usage(
            llm_output.get("token_usage") or llm_output.get("usage")
        )
        if found is not None:
            return found
    generations = getattr(response, "generations", None) or []
    for batch in generations:
        for gen in batch or []:
            message = getattr(gen, "message", None)
            if message is None:
                continue
            found = _tokens_from_usage(getattr(message, "usage_metadata", None))
            if found is not None:
                return found
            meta = getattr(message, "response_metadata", None) or {}
            if isinstance(meta, dict):
                found = _tokens_from_usage(
                    meta.get("token_usage") or meta.get("usage")
                )
                if found is not None:
                    return found
    return None


def _reply_from_response(response: Any) -> str:
    generations = getattr(response, "generations", None) or []
    for batch in generations:
        for gen in batch or []:
            message = getattr(gen, "message", None)
            if message is not None:
                return _summarize(_content_text(message))
            text = getattr(gen, "text", None)
            if text:
                return _summarize(text)
    return _summarize(response)


def _error_text(error: BaseException) -> str:
    return type(error).__name__ + ": " + str(error)


class LocalTraceHandler(BaseCallbackHandler):
    """Records chat-model and tool spans to one jsonl file. Never touches state."""

    def __init__(
        self,
        run_name: str = "run",
        run_id: str | None = None,
        path: Path | None = None,
    ) -> None:
        super().__init__()
        self.run_name = run_name
        self.run_id = run_id or uuid4().hex
        self.path = Path(path) if path is not None else _ensure_traces_dir() / (
            self.run_id + ".jsonl"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._open: dict[str, dict[str, Any]] = {}
        self._run_started = False

    def open_run(self, name: str | None = None) -> None:
        if self._run_started:
            return
        self._run_started = True
        if name:
            self.run_name = name
        self._open[self.run_id] = {
            "id": self.run_id,
            "parent_id": None,
            "name": self.run_name,
            "kind": "run",
            "started_at": _now_iso(),
            "t0": time.perf_counter(),
        }

    def close_run(self, error: BaseException | None = None) -> None:
        row = self._open.pop(self.run_id, None)
        if row is None:
            return
        duration_ms = round((time.perf_counter() - float(row.pop("t0"))) * 1000, 2)
        span = {
            "id": row["id"],
            "parent_id": None,
            "name": row["name"],
            "kind": "run",
            "status": "error" if error is not None else "ok",
            "started_at": row["started_at"],
            "ended_at": _now_iso(),
            "duration_ms": duration_ms,
        }
        if error is not None:
            span["error"] = _error_text(error)
        self._write(span)

    def _write(self, span: dict[str, Any]) -> None:
        line = json.dumps(span, ensure_ascii=True, default=str)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _parent(self, parent_run_id: UUID | None) -> str:
        pid = _sid(parent_run_id)
        if pid and pid in self._open:
            return pid
        return self.run_id

    def _begin(
        self,
        run_id: str,
        *,
        name: str,
        kind: str,
        parent_id: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.open_run()
        row: dict[str, Any] = {
            "id": run_id,
            "parent_id": parent_id or self.run_id,
            "name": name,
            "kind": kind,
            "started_at": _now_iso(),
            "t0": time.perf_counter(),
        }
        if extra:
            row.update(extra)
        self._open[run_id] = row

    def _finish(
        self,
        run_id: str,
        *,
        status: str = "ok",
        extra: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        row = self._open.pop(run_id, None)
        if row is None:
            return
        duration_ms = round((time.perf_counter() - float(row.pop("t0"))) * 1000, 2)
        span = {
            "id": row.pop("id"),
            "parent_id": row.pop("parent_id"),
            "name": row.pop("name"),
            "kind": row.pop("kind"),
            "status": status,
            "started_at": row.pop("started_at"),
            "ended_at": _now_iso(),
            "duration_ms": duration_ms,
        }
        span.update(row)
        if extra:
            span.update(extra)
        if error:
            span["error"] = error
            span["status"] = "error"
        self._write(span)

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        name = ""
        if isinstance(serialized, dict):
            name = str(serialized.get("name") or serialized.get("id") or "")
        self._begin(
            _sid(run_id),
            name=name or "chat_model",
            kind="chat_model",
            parent_id=self._parent(parent_run_id),
            extra={"prompt": _messages_summary(messages)},
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        tokens = _tokens_from_response(response)
        extra: dict[str, Any] = {"reply": _reply_from_response(response)}
        if tokens is not None:
            extra["tokens"] = tokens
        self._finish(_sid(run_id), extra=extra)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._finish(_sid(run_id), status="error", error=_error_text(error))

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        name = ""
        if isinstance(serialized, dict):
            name = str(serialized.get("name") or "")
        args = inputs if inputs is not None else input_str
        self._begin(
            _sid(run_id),
            name=name or "tool",
            kind="tool",
            parent_id=self._parent(parent_run_id),
            extra={"tool": name or "tool", "args": args},
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._finish(
            _sid(run_id),
            extra={"result": _summarize(output)},
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._finish(_sid(run_id), status="error", error=_error_text(error))


@contextmanager
def trace(run_name: str) -> Iterator[LocalTraceHandler]:
    """Open a run span. Records model and tool spans. Never writes state."""
    handler = LocalTraceHandler(run_name=run_name)
    handler.open_run(run_name)
    error: BaseException | None = None
    try:
        yield handler
    except BaseException as exc:
        error = exc
        raise
    finally:
        handler.close_run(error)


def _langsmith_enabled() -> bool:
    flag = os.environ.get("LANGSMITH_TRACING", "").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        flag = os.environ.get("LANGCHAIN_TRACING_V2", "").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        return False
    key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not key:
        key = os.environ.get("LANGCHAIN_API_KEY", "").strip()
    return bool(key)


def _print_hosted_trace_hint() -> None:
    """Print where a hosted trace would appear. Never invent a run URL."""
    if not _langsmith_enabled():
        return
    project = (
        os.environ.get("LANGSMITH_PROJECT", "").strip()
        or os.environ.get("LANGCHAIN_PROJECT", "").strip()
        or "default"
    )
    print("langsmith_tracing true")
    print("langsmith_project", project)
    print(
        "hosted_trace LangSmith records this run in that project when the "
        "key is set. This process has no hosted run id, so it does not "
        "print a URL."
    )


def traced_invoke(graph: Any, inputs: Any, config: dict[str, Any] | None = None, **kw: Any):
    """Attach LocalTraceHandler through config['callbacks'] and invoke.

    Returns (output, trace_path). If the graph raises, the exception
    propagates after the run span is closed; last_trace_path still holds
    the file. When LANGSMITH_TRACING is true and LANGSMITH_API_KEY is set,
    the env vars do the hosted trace. This function does not fake a URL.
    """
    global last_trace_path
    cfg = dict(config or {})
    run_name = str(kw.pop("run_name", None) or "invoke")
    _print_hosted_trace_hint()
    with trace(run_name) as handler:
        last_trace_path = handler.path
        callbacks = list(cfg.get("callbacks") or [])
        callbacks.append(handler)
        cfg["callbacks"] = callbacks
        output = graph.invoke(inputs, cfg, **kw)
        return output, handler.path


def render_waterfall(trace_path: str | Path) -> str:
    """Render spans as an indented waterfall. Failing spans are marked FAIL."""
    path = Path(trace_path)
    if not path.is_file():
        return "no trace at " + path.as_posix()
    spans: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        spans.append(json.loads(line))
    if not spans:
        return "empty trace"
    by_id = {str(row.get("id")): row for row in spans}
    run_id = None
    for row in spans:
        if row.get("kind") == "run":
            run_id = str(row.get("id"))
            break
    children: dict[str, list[dict[str, Any]]] = {}
    roots: list[dict[str, Any]] = []
    for row in spans:
        parent = row.get("parent_id")
        parent_s = str(parent) if parent else ""
        if row.get("kind") != "run" and parent_s not in by_id:
            parent_s = run_id or ""
        if not parent_s or parent_s not in by_id or parent_s == str(row.get("id")):
            roots.append(row)
            continue
        children.setdefault(parent_s, []).append(row)
    for group in children.values():
        group.sort(key=lambda r: float(r.get("duration_ms") or 0), reverse=True)
        group.sort(key=lambda r: str(r.get("started_at") or ""))

    lines: list[str] = []

    def walk(row: dict[str, Any], depth: int) -> None:
        indent = "  " * depth
        kind = str(row.get("kind") or "span")
        name = str(row.get("name") or kind)
        duration = row.get("duration_ms")
        dur = str(duration) + "ms" if duration is not None else "?"
        status = str(row.get("status") or "ok")
        fail = " FAIL" if status == "error" else ""
        extra = ""
        tokens = row.get("tokens")
        if isinstance(tokens, dict) and tokens.get("total") is not None:
            extra += " tokens=" + str(tokens.get("total"))
        if row.get("error"):
            extra += " " + str(row.get("error"))
        elif row.get("reply"):
            extra += " reply=" + _summarize(row.get("reply"), 80)
        elif row.get("result"):
            extra += " result=" + _summarize(row.get("result"), 80)
        lines.append(indent + kind + " " + name + " " + dur + fail + extra)
        for child in children.get(str(row.get("id")), []):
            walk(child, depth + 1)

    seen: set[str] = set()
    for row in roots:
        rid = str(row.get("id"))
        if rid in seen:
            continue
        seen.add(rid)
        walk(row, 0)
    return "\n".join(lines)


class FailState(TypedDict, total=False):
    ticket: str
    order_id: str
    carrier: dict[str, Any]


def _order_id_from_ticket(ticket: str) -> str:
    match = re.search(r"DF-\d+", (ticket or "").upper())
    return match.group(0) if match else "DF-1002"


def stash_ticket(state: FailState) -> dict[str, Any]:
    ticket = str(state.get("ticket") or "")
    order_id = str(state.get("order_id") or "") or _order_id_from_ticket(ticket)
    return {"ticket": ticket, "order_id": order_id}


def carrier_node(state: FailState, config: RunnableConfig) -> dict[str, Any]:
    """Call the flaky carrier tool so a tool span can fail for real."""
    order_id = str(state.get("order_id") or "DF-1002")
    result = fetch_carrier_status.invoke({"order_id": order_id}, config)
    return {"carrier": result}


def build_failing_carrier_graph(checkpointer=None):
    """One stash node, then the flaky carrier tool. Teaching graph for traces."""
    if checkpointer is None:
        checkpointer = InMemorySaver()
    builder = StateGraph(FailState)
    builder.add_node("stash", stash_ticket)
    builder.add_node("carrier", carrier_node)
    builder.add_edge(START, "stash")
    builder.add_edge("stash", "carrier")
    builder.add_edge("carrier", END)
    return builder.compile(checkpointer=checkpointer)
