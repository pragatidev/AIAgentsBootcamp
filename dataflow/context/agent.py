"""Plain loop for Part 3: read_file, notes, compaction hooks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import tiktoken

CONTEXT_DIR = Path(__file__).resolve().parent
NOTES_PATH = CONTEXT_DIR / "notes.json"
KB_ROOT = Path(__file__).resolve().parents[1] / "knowledge_base"
WIKI_ROOT = Path(__file__).resolve().parents[1] / "wiki"
DATA_ROOT = Path(__file__).resolve().parents[1] / "data"

SUMMARIZE_PROMPT = (
    "Summarize the older DataFlow desk turns. "
    "Shape: facts, actions, decisions, open questions. "
    "Keep order ids, customer names, amounts, and stated constraints. "
    "No preamble."
)

READ_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a DataFlow knowledge file by name from the map.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File name such as return_policy.md",
                }
            },
            "required": ["path"],
        },
    },
}

NOTE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_note",
        "description": "Write a named fact to the notes file. Key is short. Value is one sentence.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short name such as constraint"},
                "value": {"type": "string", "description": "The fact in one sentence"},
            },
            "required": ["key", "value"],
        },
    },
}

_ALLOWED_NAMES = {
    "return_policy.md": WIKI_ROOT / "return_policy.md",
    "shipping.md": WIKI_ROOT / "shipping.md",
    "billing_and_pricing.csv": KB_ROOT
    / "business_data"
    / "billing_and_pricing.csv",
    "product_user_guide.markdown": KB_ROOT
    / "customer_facing"
    / "product_user_guide.markdown",
    "troubleshooting_guide.txt": KB_ROOT
    / "customer_facing"
    / "troubleshooting_guide.txt",
    "terms_of_service.markdown": KB_ROOT
    / "customer_facing"
    / "terms_of_service.markdown",
    "api_documentation.json": KB_ROOT
    / "customer_facing"
    / "api_documentation.json",
    "customer_support_procedures.markdown": KB_ROOT
    / "internal_operations"
    / "support_operations"
    / "customer_support_procedures.markdown",
    "orders.json": DATA_ROOT / "orders.json",
    "privacy_policy.txt": KB_ROOT / "legal_compliance" / "privacy_policy.txt",
    "employee_handbook.txt": KB_ROOT
    / "internal_operations"
    / "hr_policies"
    / "employee_handbook.txt",
    "competitive_analysis.txt": KB_ROOT
    / "customer_facing"
    / "competitive_analysis.txt",
}


def _enc():
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(messages: list) -> int:
    parts = []
    for msg in messages:
        parts.append(str(msg.get("role") or ""))
        parts.append(str(msg.get("content") or ""))
    return len(_enc().encode("\n".join(parts)))


def read_file(path: str) -> str:
    """Read a knowledge base or wiki file by its map name."""
    name = Path(str(path or "").strip()).name
    target = _ALLOWED_NAMES.get(name)
    if target is None or not target.is_file():
        return json.dumps({"found": False, "path": name, "reason": "unknown file"})
    text = target.read_text(encoding="utf-8")
    if len(text) > 4000:
        text = text[:4000] + "\n...[truncated]"
    return json.dumps({"found": True, "path": name, "text": text})


def load_notes(path: Path = NOTES_PATH) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_note(key: str, value: str, path: Path = NOTES_PATH) -> str:
    notes = load_notes(path)
    notes[str(key)] = str(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notes, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return json.dumps(notes)


def compact_messages(
    messages: list,
    *,
    threshold: int,
    keep_last: int,
    summariser: Callable[[str], str],
) -> tuple[list, bool, int, int]:
    """Replace older messages with a summary once tokens pass the threshold."""
    before = count_tokens(messages)
    if before <= threshold:
        return messages, False, before, before
    keep_n = max(keep_last, 0)
    keep = messages[-keep_n:] if keep_n else []
    older = messages[:-keep_n] if keep_n else list(messages)
    system = [m for m in older if m.get("role") == "system"][:1]
    body = [m for m in older if m.get("role") != "system"]
    blob = "\n".join(
        f"{m.get('role')}: {m.get('content')}" for m in body
    )
    summary = summariser(blob)
    new = system + [
        {"role": "assistant", "content": "SUMMARY\n" + str(summary)}
    ] + keep
    after = count_tokens(new)
    return new, True, before, after


def chat_caller(num_predict: int = 80):
    """Plain chat, no tools. Used by the rot and compaction labs."""
    import config

    model = config.get_local_chat_model(reasoning=False, num_predict=num_predict)

    def call(messages: list) -> dict:
        reply = model.invoke(messages)
        meta = getattr(reply, "usage_metadata", None) or {}
        return {
            "content": str(getattr(reply, "content", "")),
            "tool_calls": [],
            "usage": {
                "input_tokens": meta.get("input_tokens"),
                "output_tokens": meta.get("output_tokens"),
                "total_tokens": meta.get("total_tokens"),
            },
        }

    return call


def context_caller(*, enable_read: bool = True, enable_notes: bool = True):
    from techcorp.agent.scratch import openai_caller

    schemas: list[dict] = []
    if enable_read:
        schemas.append(READ_SCHEMA)
    if enable_notes:
        schemas.append(NOTE_SCHEMA)
    return openai_caller(schemas)


def default_summariser(text: str) -> str:
    import config

    chat = config.get_local_chat_model(reasoning=False, num_predict=160)
    reply = chat.invoke(
        [
            {"role": "system", "content": SUMMARIZE_PROMPT},
            {"role": "user", "content": text[:6000]},
        ]
    )
    return str(getattr(reply, "content", reply))


def _usage(reply: Any) -> dict:
    if isinstance(reply, dict):
        return reply.get("usage") or {}
    meta = getattr(reply, "usage_metadata", None) or {}
    return {
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "total_tokens": meta.get("total_tokens"),
    }


class ContextAgent:
    """Loop with optional read_file, write_note, and compaction."""

    def __init__(
        self,
        call_model: Callable[[list], dict],
        *,
        system: str,
        tools: dict[str, Callable] | None = None,
        compact: bool = False,
        compact_threshold: int = 800,
        keep_last: int = 6,
        summariser: Callable[[str], str] | None = None,
        notes_path: Path = NOTES_PATH,
        cap: int = 8,
        preload: str | None = None,
    ) -> None:
        self.call_model = call_model
        self.system = system
        self.tools = tools or {}
        self.compact = compact
        self.compact_threshold = compact_threshold
        self.keep_last = keep_last
        self.summariser = summariser or default_summariser
        self.notes_path = notes_path
        self.cap = cap
        self.preload = preload
        self.token_trace: list[dict] = []
        self.reads: list[str] = []

    def _system_text(self) -> str:
        text = self.system
        if self.preload:
            text = text + "\n\nPRELOADED\n" + self.preload
        notes = load_notes(self.notes_path)
        if notes:
            text = text + "\n\nNOTES\n" + json.dumps(notes)
        return text

    def _maybe_compact(self, messages: list) -> list:
        if not self.compact:
            return messages
        new, folded, before, after = compact_messages(
            messages,
            threshold=self.compact_threshold,
            keep_last=self.keep_last,
            summariser=self.summariser,
        )
        if folded:
            self.token_trace.append(
                {
                    "event": "compact",
                    "tokens_before": before,
                    "tokens_after": after,
                }
            )
        return new

    def _run_tools(self, messages: list, ticket: str) -> dict:
        messages = list(messages)
        tool_names: list[str] = []
        for n in range(1, self.cap + 1):
            messages = self._maybe_compact(messages)
            reply = self.call_model(messages)
            usage = _usage(reply)
            content = reply.get("content") or ""
            calls = list(reply.get("tool_calls") or [])
            self.token_trace.append(
                {
                    "event": "model",
                    "round": n,
                    "tokens": count_tokens(messages),
                    "usage": usage,
                    "tools": [c.get("name") for c in calls],
                }
            )
            if not calls:
                messages.append({"role": "assistant", "content": content})
                return {
                    "final": content,
                    "messages": messages,
                    "tool_names": tool_names,
                    "stop": "final",
                    "token_trace": list(self.token_trace),
                    "notes": load_notes(self.notes_path),
                    "reads": list(self.reads),
                }
            raw = reply.get("raw_tool_calls") or []
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": raw
                    or [
                        {
                            "id": c.get("id"),
                            "type": "function",
                            "function": {
                                "name": c.get("name"),
                                "arguments": c.get("arguments_json")
                                or json.dumps(c.get("arguments") or {}),
                            },
                        }
                        for c in calls
                    ],
                }
            )
            for call in calls:
                name = str(call.get("name") or "")
                args = call.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args) if args else {}
                tool_names.append(name)
                if name == "read_file":
                    path = str(args.get("path") or "")
                    self.reads.append(path)
                    result = read_file(path)
                elif name == "write_note":
                    result = write_note(
                        str(args.get("key") or ""),
                        str(args.get("value") or ""),
                        path=self.notes_path,
                    )
                elif name in self.tools:
                    fn = self.tools[name]
                    result = fn(**args) if args else fn()
                else:
                    result = json.dumps({"ok": False, "reason": "unknown tool"})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": str(result),
                    }
                )
        return {
            "final": "desk could not finish",
            "messages": messages,
            "tool_names": tool_names,
            "stop": "cap",
            "token_trace": list(self.token_trace),
            "notes": load_notes(self.notes_path),
            "reads": list(self.reads),
        }

    def run(self, ticket: str) -> dict:
        self.token_trace = []
        self.reads = []
        messages = [
            {"role": "system", "content": self._system_text()},
            {"role": "user", "content": ticket},
        ]
        return self._run_tools(messages, ticket)

    def run_turns(self, turns: list[str]) -> dict:
        """Multi-turn conversation. Compaction may fold between turns."""
        self.token_trace = []
        messages = [{"role": "system", "content": self._system_text()}]
        replies: list[str] = []
        for i, turn in enumerate(turns, start=1):
            messages = self._maybe_compact(messages)
            messages.append({"role": "user", "content": turn})
            before = count_tokens(messages)
            reply = self.call_model(messages)
            content = reply.get("content") or ""
            usage = _usage(reply)
            messages.append({"role": "assistant", "content": content})
            replies.append(content)
            self.token_trace.append(
                {
                    "turn": i,
                    "tokens": before,
                    "usage": usage,
                    "text": content,
                }
            )
        return {
            "messages": messages,
            "replies": replies,
            "token_trace": list(self.token_trace),
            "notes": load_notes(self.notes_path),
        }
