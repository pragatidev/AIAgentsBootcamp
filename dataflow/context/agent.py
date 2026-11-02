"""Plain loop for Part 3: read_file, notes, compaction hooks."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import tiktoken

from dataflow.context.guard import guard_read
from dataflow.context.redact import redact

CONTEXT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
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

MY_ORDER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "lookup_my_order",
        "description": "Look up one of this customer's own orders by its id, such as DF-1001.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Order id such as DF-1001"}},
            "required": ["order_id"],
        },
    },
}

_ALLOWED_NAMES = {
    "return_policy.md": WIKI_ROOT / "return_policy.md",
    "shipping.md": WIKI_ROOT / "shipping.md",
    "security.md": WIKI_ROOT / "security.md",
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


def repo_path(path: Path) -> str:
    """A path as it looks from the repo root, so the screen matches every student's machine."""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def applied_window() -> int | None:
    """The context window the Ollama server applied to the chat model, read from /api/ps.

    The server reports it after a call has loaded the model. None when the
    server cannot be reached or reports no context length.
    """
    import urllib.error
    import urllib.request

    import config

    url = config.OLLAMA_BASE_URL.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    try:
        with urllib.request.urlopen(url + "/api/ps", timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    for item in payload.get("models") or []:
        if str(item.get("name") or "") == config.CHAT_MODEL or str(item.get("model") or "") == config.CHAT_MODEL:
            ctx = item.get("context_length")
            return int(ctx) if ctx else None
    return None


def count_tokens(messages: list) -> int:
    parts = []
    for msg in messages:
        parts.append(str(msg.get("role") or ""))
        parts.append(str(msg.get("content") or ""))
    return len(_enc().encode("\n".join(parts)))


# The files a customer desk may read: the map's files without the two the map says are never for a
# customer, and without orders.json, which holds every customer's orders (lookup_my_order reads one).
CUSTOMER_FILES = frozenset(_ALLOWED_NAMES) - {"employee_handbook.txt", "competitive_analysis.txt", "orders.json"}


def read_file(path: str, allowed: set[str] | frozenset[str] | None = None, guard: Any = None) -> str:
    """Read a knowledge base or wiki file by its map name.

    Only the last part of the path counts, so ../../.env is just .env, which is not on the list.
    allowed is the role's list; a name outside it is refused even when the file exists.
    guard True runs guard_read (strip instruction lines, mask secrets, box); a function runs that instead.
    """
    name = Path(str(path or "").strip()).name
    target = _ALLOWED_NAMES.get(name)
    if target is None or not target.is_file():
        return json.dumps({"found": False, "path": name, "reason": "unknown file"})
    if allowed is not None and name not in allowed:
        return json.dumps({"found": False, "path": name, "reason": "not on this desk's list"})
    text = target.read_text(encoding="utf-8")
    if len(text) > 4000:
        text = text[:4000] + "\n...[truncated]"
    if guard:
        text, dropped = (guard_read if guard is True else guard)(name, text)
        return json.dumps({"found": True, "path": name, "text": text, "dropped_lines": dropped})
    return json.dumps({"found": True, "path": name, "text": text})


def lookup_my_order(order_id: str, customer_id: str | None) -> str:
    """One order, only when it belongs to the customer this desk serves. Another customer's order is a typed miss."""
    orders = json.loads((DATA_ROOT / "orders.json").read_text(encoding="utf-8"))
    key = str(order_id or "").strip().upper()
    row = orders.get(key)
    if row is None:
        return json.dumps({"found": False, "order_id": key, "reason": "unknown order"})
    if not customer_id or row.get("customer_id") != customer_id:
        return json.dumps({"found": False, "order_id": key, "reason": "not this customer's order"})
    return json.dumps({"found": True, "order_id": key, **row})


def notes_path_for(customer_id: str) -> Path:
    """One notes file per customer, dataflow/context/notes/<customer_id>.json."""
    if not customer_id or not all(ch.isalnum() or ch == "-" for ch in customer_id):
        raise ValueError(f"not a customer id: {customer_id!r}")
    return CONTEXT_DIR / "notes" / f"{customer_id}.json"


def load_notes(path: Path = NOTES_PATH) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# A note under one of these keys is written once. Changing it is a person's job, not the model's.
PROTECTED_KEYS = frozenset({"constraint"})


def write_note(key: str, value: str, path: Path = NOTES_PATH) -> str:
    """Write one named fact. A protected key that already holds a value is refused and the file is left alone."""
    notes = load_notes(path)
    key = str(key)
    if key in PROTECTED_KEYS and key in notes:
        return json.dumps({"ok": False, "key": key, "reason": "protected key, ask a person"})
    notes[key] = str(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notes, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return json.dumps({"ok": True, "key": key, "notes": notes})


def notes_block(path: Path = NOTES_PATH) -> str:
    """The notes as the desk's system message carries them, or nothing when there are none."""
    notes = load_notes(path)
    if not notes:
        return ""
    return "\n\nNOTES\n" + json.dumps(notes)


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
    cut = max(len(messages) - keep_n, 0) if keep_n else len(messages)
    # The kept tail never starts with a tool result whose call was folded away: move the cut back
    # to the assistant message that made the call, so the call and its results stay together.
    while 0 < cut < len(messages) and messages[cut].get("role") == "tool":
        cut -= 1
    keep = messages[cut:]
    older = messages[:cut]
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


def chat_caller(num_predict: int = 80, num_ctx: int | None = None, tools: list[dict] | None = None):
    """The local model through config.py, as one function: messages in, a reply dict out.

    num_ctx is the context window in tokens. None leaves it to the Ollama
    server's default; a number makes the window a setting you can print.
    tools are function schemas bound to the model; with none it is plain chat.
    """
    import config

    extra = {} if num_ctx is None else {"num_ctx": int(num_ctx)}
    model = config.get_local_chat_model(reasoning=False, num_predict=num_predict, **extra)
    if tools:
        model = model.bind_tools(tools)

    def call(messages: list) -> dict:
        reply = model.invoke(messages)
        meta = getattr(reply, "usage_metadata", None) or {}
        calls = []
        raw = []
        for item in getattr(reply, "tool_calls", None) or []:
            args = item.get("args") or {}
            calls.append({"id": item.get("id"), "name": item.get("name"), "arguments": args})
            raw.append(
                {
                    "id": item.get("id"),
                    "type": "function",
                    "function": {"name": item.get("name"), "arguments": json.dumps(args)},
                }
            )
        return {
            "content": str(getattr(reply, "content", "")),
            "tool_calls": calls,
            "raw_tool_calls": raw,
            "usage": {
                "input_tokens": meta.get("input_tokens"),
                "output_tokens": meta.get("output_tokens"),
                "total_tokens": meta.get("total_tokens"),
            },
        }

    call.tool_names = [t["function"]["name"] for t in tools or []]
    call.model = config.CHAT_MODEL
    return call


def context_caller(
    *,
    enable_read: bool = True,
    enable_notes: bool = True,
    num_ctx: int | None = None,
    extra_schemas: list[dict] | None = None,
    enable_orders: bool = False,
):
    """chat_caller with the desk's tools bound: read_file, write_note, lookup_my_order, and any extra schemas."""
    schemas: list[dict] = []
    if enable_read:
        schemas.append(READ_SCHEMA)
    if enable_notes:
        schemas.append(NOTE_SCHEMA)
    if enable_orders:
        schemas.append(MY_ORDER_SCHEMA)
    schemas.extend(extra_schemas or [])
    return chat_caller(num_predict=512, num_ctx=num_ctx, tools=schemas)


def summarise_with_usage(text: str, prompt: str = SUMMARIZE_PROMPT) -> tuple[str, dict]:
    """One real summariser call. Returns the summary and the server's count for that call."""
    import config

    chat = config.get_local_chat_model(reasoning=False, num_predict=160)
    reply = chat.invoke(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text[:6000]},
        ]
    )
    return str(getattr(reply, "content", reply)), _usage(reply)


def default_summariser(text: str) -> str:
    return summarise_with_usage(text)[0]


def total_input(trace: list) -> dict:
    """What a run read, from its trace: the desk's calls, the summariser's calls, and both together.

    The server's count where there is one, the library's where there is not.
    """
    desk = 0
    summariser = 0
    for row in trace:
        if row.get("event") == "compact":
            summariser += int((row.get("summariser_usage") or {}).get("input_tokens") or 0)
        elif row.get("turn") or row.get("event") == "model":
            usage = row.get("usage") or {}
            desk += int(usage.get("input_tokens") or row.get("tokens") or 0)
    return {"desk": desk, "summariser": summariser, "total": desk + summariser}


def _usage(reply: Any) -> dict:
    """The server's count in one shape: input_tokens, output_tokens, total_tokens.

    LangChain's usage_metadata already uses those names. The OpenAI SDK says
    prompt_tokens and completion_tokens, so those are mapped across.
    """
    if isinstance(reply, dict):
        usage = reply.get("usage") or {}
        if "prompt_tokens" in usage and "input_tokens" not in usage:
            details = usage.get("prompt_tokens_details") or {}
            return {
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "cached_tokens": details.get("cached_tokens"),
            }
        return usage
    meta = getattr(reply, "usage_metadata", None) or {}
    return {
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "total_tokens": meta.get("total_tokens"),
    }


_notes_block = notes_block


class ContextAgent:
    """Loop with optional read_file, write_note, compaction, a token budget and a window log."""

    def __init__(
        self,
        call_model: Callable[[list], dict],
        *,
        system: str,
        tools: dict[str, Callable] | None = None,
        compact: bool = False,
        compact_threshold: int = 800,
        keep_last: int = 6,
        summariser: Callable[[str], Any] | None = None,
        notes_path: Path | None = None,
        cap: int = 8,
        preload: str | None = None,
        compactor: Callable[..., tuple] | None = None,
        note_writer: Callable[..., str] | None = None,
        notes_block: Callable[[Path], str] | None = None,
        reader: Callable[[str], str] | None = None,
        customer_id: str | None = None,
        allowed: set[str] | frozenset[str] | None = None,
        guard: Any = None,
        budget: int | None = None,
        on_over: str = "compact",
        stable_prefix: bool = False,
        window_log: Path | None = None,
        run_id: str | None = None,
        map_version: str | None = None,
    ) -> None:
        self.call_model = call_model
        self.system = system
        self.tools = tools or {}
        self.compact = compact
        self.compact_threshold = compact_threshold
        self.keep_last = keep_last
        # A summariser returns the summary, or (summary, usage) when it can report its own count.
        self.summariser = summariser or summarise_with_usage
        # The fold itself. Lab 5.8 passes the one you typed; every other lab uses compact_messages.
        self.compactor = compactor or compact_messages
        # The write path and the notes block. Labs 5.11 and 5.12 pass the ones you typed.
        self.note_writer = note_writer or write_note
        self.notes_block = notes_block or _notes_block
        # The read tool. Lab 5.14 passes the read_file you typed.
        self.reader = reader or (lambda path: read_file(path, allowed=self.allowed, guard=self.guard))
        # The customer this desk serves. With one set, the notes file is that customer's own.
        self.customer_id = customer_id
        if notes_path is None and customer_id:
            notes_path = notes_path_for(customer_id)
        # No notes file unless one is passed, so one lab's notes never leak into another lab's desk.
        self.notes_path = notes_path
        # The role's list of files, and the guard on what a read and a ticket put in the window.
        self.allowed = allowed
        self.guard = guard
        self.cap = cap
        self.preload = preload
        # The budget is checked on the library count of every call before it is sent. Over it, the desk
        # folds ("compact") or stops ("refuse"); still over after a fold, it stops with stop "budget".
        self.budget = budget
        self.on_over = on_over
        # A stable prefix keeps the first message the same for the whole run: the notes travel as a
        # second message, rebuilt on every call, so a note write never changes the first message.
        self.stable_prefix = stable_prefix
        self.window_log = Path(window_log) if window_log else None
        self.run_id = run_id or "run"
        self.map_version = map_version
        self._reset()

    def _reset(self) -> None:
        self.token_trace: list[dict] = []
        self.reads: list[str] = []
        self.writes: list[dict] = []
        self.dropped: list[str] = []
        self.calls = 0
        self.tool_sources: dict[str, str] = {}
        self.last_window: list[dict] = []

    # The window: what the model is sent on a call.

    def _inbound(self, text: str) -> str:
        """A customer's words as they enter the window: secrets and emails masked when the desk is guarded."""
        return redact(text) if self.guard else text

    def _notes(self) -> dict:
        return {} if self.notes_path is None else load_notes(self.notes_path)

    def _prefix(self) -> str:
        text = self.system
        if self.preload:
            text = text + "\n\nPRELOADED\n" + self.preload
        return text

    def _system_text(self) -> str:
        if self.notes_path is None:
            return self._prefix()
        return self._prefix() + self.notes_block(self.notes_path)

    def _first_message(self) -> dict:
        return {"role": "system", "content": self._prefix() if self.stable_prefix else self._system_text()}

    def window(self, messages: list) -> list:
        """What the model is sent for this call: the stored messages with the notes as they are now."""
        if not messages or self.notes_path is None:
            return list(messages)
        if self.stable_prefix:
            block = self.notes_block(self.notes_path).strip()
            notes = [{"role": "system", "content": block}] if block else []
            return messages[:1] + notes + messages[1:]
        return [{"role": "system", "content": self._system_text()}] + messages[1:]

    # Folding and the budget.

    def _fold(self, messages: list, threshold: int, reason: str) -> list:
        if len(messages) <= self.keep_last + 1:
            return messages  # nothing older than the kept tail to fold
        usages: list[dict] = []

        def summarise(text: str) -> str:
            out = self.summariser(text)
            summary, usage = out if isinstance(out, tuple) else (out, {})
            usages.append(usage or {})
            return summary

        new, folded, before, after = self.compactor(
            messages,
            threshold=threshold,
            keep_last=self.keep_last,
            summariser=summarise,
        )
        if folded:
            summary = next(
                (
                    str(m.get("content"))
                    for m in new
                    if m.get("role") == "assistant" and str(m.get("content") or "").startswith("SUMMARY")
                ),
                "",
            )
            self.token_trace.append(
                {
                    "event": "compact",
                    "reason": reason,
                    "tokens_before": before,
                    "tokens_after": after,
                    "summary": summary,
                    "summariser_usage": usages[-1] if usages else {},
                }
            )
        return new

    def _maybe_compact(self, messages: list) -> list:
        if not self.compact:
            return messages
        return self._fold(messages, self.compact_threshold, "threshold")

    def _prepare(self, messages: list, fold: bool = True) -> tuple[list, list, bool]:
        """Fold if asked, build the window, check the budget. Returns (messages, window, stopped)."""
        if fold:
            messages = self._maybe_compact(messages)
        sent = self.window(messages)
        if self.budget is None or count_tokens(sent) <= self.budget:
            return messages, sent, False
        if self.on_over == "compact":
            overhead = count_tokens(sent) - count_tokens(messages)
            messages = self._fold(messages, max(self.budget - overhead, 0), "budget")
            sent = self.window(messages)
        tokens = count_tokens(sent)
        if tokens <= self.budget:
            return messages, sent, False
        self.token_trace.append({"event": "stop", "reason": "budget", "tokens": tokens, "budget": self.budget})
        return messages, sent, True

    # One model call, logged.

    def _invoke(self, sent: list) -> tuple[dict, dict]:
        start = time.perf_counter()
        reply = self.call_model(sent)
        ms = int((time.perf_counter() - start) * 1000)
        usage = _usage(reply)
        self.calls += 1
        self.last_window = sent
        if self.window_log is not None:
            from dataflow.context.window_log import log_call

            log_call(
                self.window_log,
                run_id=self.run_id,
                call_no=self.calls,
                messages=sent,
                usage=usage,
                model=str(getattr(self.call_model, "model", "") or "scripted"),
                ms=ms,
                map_version=self.map_version,
                notes_keys=sorted(self._notes()),
                reads=list(self.reads),
                tool_sources=self.tool_sources,
            )
        return reply, usage

    # Tools.

    def _run_tool(self, call: dict) -> str:
        name = str(call.get("name") or "")
        args = call.get("arguments") or {}
        if isinstance(args, str):
            args = json.loads(args) if args else {}
        if name == "read_file":
            path = str(args.get("path") or "")
            self.reads.append(path)
            self.tool_sources[call.get("id")] = "tool:read_file:" + Path(path).name
            result = self.reader(path)
            # Lines a guard dropped are kept on the desk, never sent back to the model.
            try:
                parsed = json.loads(result)
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict) and "dropped_lines" in parsed:
                self.dropped.extend(parsed.pop("dropped_lines") or [])
                result = json.dumps(parsed)
            return result
        self.tool_sources[call.get("id")] = "tool:" + name
        if name == "lookup_my_order":
            return lookup_my_order(str(args.get("order_id") or ""), self.customer_id)
        if name == "write_note":
            key = str(args.get("key") or "")
            value = str(args.get("value") or "")
            if self.notes_path is None:
                result = json.dumps({"ok": False, "key": key, "reason": "this desk has no notes file"})
            else:
                result = self.note_writer(key, value, path=self.notes_path)
            self.writes.append({"key": key, "value": value, "result": json.loads(result)})
            return result
        if name in self.tools:
            fn = self.tools[name]
            return fn(**args) if args else fn()
        return json.dumps({"ok": False, "reason": "unknown tool"})

    def _tool_loop(self, messages: list, tool_names: list[str]) -> tuple[list, str, str]:
        """Call, run any tools, call again, up to cap calls. Returns (messages, stop, final)."""
        for n in range(1, self.cap + 1):
            messages, sent, stopped = self._prepare(messages)
            if stopped:
                return messages, "budget", "over budget"
            reply, usage = self._invoke(sent)
            content = reply.get("content") or ""
            calls = list(reply.get("tool_calls") or [])
            self.token_trace.append(
                {
                    "event": "model",
                    "round": n,
                    "tokens": count_tokens(sent),
                    "usage": usage,
                    "tools": [c.get("name") for c in calls],
                }
            )
            if not calls:
                messages.append({"role": "assistant", "content": content})
                return messages, "final", content
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
                                "arguments": c.get("arguments_json") or json.dumps(c.get("arguments") or {}),
                            },
                        }
                        for c in calls
                    ],
                }
            )
            for call in calls:
                tool_names.append(str(call.get("name") or ""))
                result = self._run_tool(call)
                messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": str(result)})
        return messages, "cap", "desk could not finish"

    def _result(self, messages: list, **extra) -> dict:
        return {
            "messages": messages,
            "token_trace": list(self.token_trace),
            "notes": self._notes(),
            "reads": list(self.reads),
            "writes": list(self.writes),
            "dropped_lines": list(self.dropped),
            "last_window": list(self.last_window),
            **extra,
        }

    # The three ways to run a desk.

    def run(self, ticket: str) -> dict:
        """One ticket, with tools."""
        self._reset()
        tool_names: list[str] = []
        messages = [self._first_message(), {"role": "user", "content": self._inbound(ticket)}]
        messages, stop, final = self._tool_loop(messages, tool_names)
        return self._result(messages, final=final, tool_names=tool_names, stop=stop)

    def run_turns(self, turns: list[str], progress_every: int = 0) -> dict:
        """Multi-turn conversation, one model call per turn, no tools. Compaction may fold between turns.

        progress_every prints "turn N of M" every N turns, so a long run shows it is moving.
        """
        self._reset()
        messages = [self._first_message()]
        replies: list[str] = []
        stop = "final"
        for i, turn in enumerate(turns, start=1):
            if progress_every and (i % progress_every == 0 or i == len(turns)):
                print("turn", i, "of", len(turns), flush=True)
            messages = self._maybe_compact(messages)
            messages.append({"role": "user", "content": self._inbound(turn)})
            messages, sent, stopped = self._prepare(messages, fold=False)
            if stopped:
                stop = "budget"
                break
            reply, usage = self._invoke(sent)
            content = reply.get("content") or ""
            messages.append({"role": "assistant", "content": content})
            replies.append(content)
            self.token_trace.append({"turn": i, "tokens": count_tokens(sent), "usage": usage, "text": content})
        return self._result(messages, replies=replies, stop=stop)

    def run_session(self, turns: list[str], progress_every: int = 0) -> dict:
        """A long conversation with tools: one growing message list, the tool loop on every turn.

        Before every call the desk folds if asked, rebuilds the notes, checks the budget and logs
        the window. Each turn's row records its calls, its tools and its wall time in seconds.
        """
        self._reset()
        messages = [self._first_message()]
        replies: list[str] = []
        stop = "final"
        for i, turn in enumerate(turns, start=1):
            start = time.perf_counter()
            calls_before = self.calls
            tool_names: list[str] = []
            messages.append({"role": "user", "content": self._inbound(turn)})
            messages, turn_stop, final = self._tool_loop(messages, tool_names)
            replies.append(final)
            seconds = round(time.perf_counter() - start, 2)
            self.token_trace.append(
                {"turn": i, "calls": self.calls - calls_before, "tools": tool_names, "text": final, "seconds": seconds}
            )
            if progress_every and (i % progress_every == 0 or i == len(turns)):
                print("turn", i, "of", len(turns), "calls", self.calls - calls_before, "tools", tool_names, "seconds", seconds, flush=True)
            if turn_stop == "budget":
                stop = "budget"
                break
        return self._result(messages, replies=replies, stop=stop)
