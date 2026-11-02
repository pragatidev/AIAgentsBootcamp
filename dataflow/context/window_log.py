"""The window log: one JSON row per model call, saying what the model saw, by source, and what it cost.

A trace span summarises a message to a few hundred characters. This log keeps every message as sent
(secrets and emails masked), with its source, its hash and its token count, so a question like "was the
refund rule in front of the model on call 7?" has an answer you can read.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from dataflow.context.redact import redact

TRACES_DIR = Path(__file__).resolve().parents[1] / "data" / "traces"


def log_path(run_id: str) -> Path:
    """dataflow/data/traces/window_<run_id>.jsonl. Git ignores the folder."""
    return TRACES_DIR / f"window_{run_id}.jsonl"


def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def source_of(message: dict, index: int, tool_sources: dict | None = None) -> str:
    """Where a message came from: system, notes, summary, user, assistant, or tool:<what it read>."""
    role = message.get("role")
    content = str(message.get("content") or "")
    if role == "system":
        if index == 0:
            return "system"
        return "notes" if content.startswith("NOTES") else "system"
    if role == "tool":
        return (tool_sources or {}).get(message.get("tool_call_id"), "tool")
    if role == "assistant" and content.startswith("SUMMARY"):
        return "summary"
    return str(role)


def log_call(
    path: Path,
    *,
    run_id: str,
    call_no: int,
    messages: list,
    usage: dict,
    model: str,
    ms: int,
    map_version: str | None = None,
    notes_keys: list | None = None,
    reads: list | None = None,
    event: str = "model",
    tool_sources: dict | None = None,
) -> dict:
    """Append one row for one model call and return it."""
    from dataflow.context.agent import count_tokens

    usage = usage or {}
    total = usage.get("total_tokens") or (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
    row = {
        "request_id": f"{run_id}-{call_no:03d}",
        "run_id": run_id,
        "call_no": call_no,
        "event": event,
        "model": model,
        "ms": ms,
        "tokens": {"total": total, "input": usage.get("input_tokens"), "output": usage.get("output_tokens")},
        "window_tokens": count_tokens(messages),
        "map_version": map_version,
        "notes_keys": list(notes_keys or []),
        "reads": list(reads or []),
        "prefix_sha256": sha256(str(messages[0].get("content") or "")) if messages else None,
        "messages": [
            {
                "role": m.get("role"),
                "source": source_of(m, i, tool_sources),
                "sha256": sha256(str(m.get("content") or "")),
                "tokens": count_tokens([m]),
                "text": redact(str(m.get("content") or "")),
            }
            for i, m in enumerate(messages)
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")
    return row


def where_in_window(row: dict, text: str) -> list[str]:
    """The sources of the messages in one logged call that contain text, ignoring case."""
    return [m["source"] for m in row["messages"] if text.lower() in m["text"].lower()]


def read_log(path: Path) -> list[dict]:
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
