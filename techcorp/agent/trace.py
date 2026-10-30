"""A trace of a desk run with no payload: what ran, for how long, and how many tokens, never a message or a value.

LangGraph's TracePolicy(process_inputs=omit_payload) shapes what one node's own span records, and its
docstring says it is not meant to redact secrets; a tool span still records the tool's result. This
handler keeps the span and drops the payload: for a tool it writes the keys of the result, not the values.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from techcorp.tools.accounts import SECRET_KEYS

TRACES_DIR = Path(__file__).resolve().parents[1] / "data" / "traces"


def _result_keys(output: Any) -> list[str]:
    content = getattr(output, "content", output)
    try:
        value = json.loads(content) if isinstance(content, str) else content
    except ValueError:
        return []
    if isinstance(value, dict):
        return sorted(key for key in value if key not in SECRET_KEYS) + sorted(key + " (withheld)" for key in value if key in SECRET_KEYS)
    return []


class SafeTrace(BaseCallbackHandler):
    """One jsonl row per model call and per tool call, with timings and token counts and no payload."""

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self.path = Path(path) if path is not None else TRACES_DIR / f"{int(time.time())}.jsonl"
        self._started: dict[UUID, tuple[str, float]] = {}

    def _row(self, row: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    def on_chat_model_start(self, serialized, messages, *, run_id: UUID, **kwargs: Any) -> None:
        self._started[run_id] = ("model", time.perf_counter())

    def on_llm_end(self, response, *, run_id: UUID, **kwargs: Any) -> None:
        _, t0 = self._started.pop(run_id, ("model", time.perf_counter()))
        message = getattr(response.generations[0][0], "message", None) if response.generations else None
        usage = getattr(message, "usage_metadata", None) or {}
        calls = [c["name"] for c in getattr(message, "tool_calls", None) or []]
        self._row({"kind": "model", "ms": round((time.perf_counter() - t0) * 1000, 1), "total_tokens": usage.get("total_tokens"), "asked_for": calls})

    def on_tool_start(self, serialized, input_str, *, run_id: UUID, inputs: dict | None = None, **kwargs: Any) -> None:
        name = (serialized or {}).get("name") or "tool"
        self._started[run_id] = (name, time.perf_counter())

    def on_tool_end(self, output, *, run_id: UUID, **kwargs: Any) -> None:
        name, t0 = self._started.pop(run_id, ("tool", time.perf_counter()))
        self._row({"kind": "tool", "tool": name, "ms": round((time.perf_counter() - t0) * 1000, 1), "result_keys": _result_keys(output)})
