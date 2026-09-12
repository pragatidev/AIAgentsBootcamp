"""Coding loop inside techcorp/harness/sandbox/.

cwd is locked. Every path is resolved and must stay under root. A write
to ../../README.md is a typed miss. run_tests runs pytest on this folder
only. A step cap ends a looping script.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from config import get_chat_model

SANDBOX = Path(__file__).resolve().parent / "sandbox"
STOPPED = "STOPPED: step cap"
DEFAULT_CAP = 8

SANDBOX_SYSTEM = (
    "You are a coding agent. You may read, write, and test files only "
    "inside the sandbox folder. Paths outside the sandbox are a miss. "
    "Edit fixture.py so test_add passes, then call run_tests. Stop when "
    "the test passes."
)


def resolve_in_root(path: str, root: Path) -> Path | dict:
    """Return the resolved path, or a typed miss if it leaves root."""
    root = Path(root).resolve()
    raw = Path(path)
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return {
            "denied": True,
            "tool": "write_file",
            "reason": "path is outside the sandbox root",
            "path": path,
        }
    return candidate


def write_under_root(path: str, content: str, root: Path | None = None) -> dict:
    """Write one file if it stays under root. Used by the lab break and the tool."""
    box = Path(root) if root is not None else SANDBOX
    resolved = resolve_in_root(path, box)
    if isinstance(resolved, dict):
        return resolved
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return {"path": str(resolved), "wrote": True, "chars": len(content)}


def read_under_root(path: str, root: Path | None = None) -> dict:
    box = Path(root) if root is not None else SANDBOX
    resolved = resolve_in_root(path, box)
    if isinstance(resolved, dict):
        resolved["tool"] = "read_file"
        return resolved
    if not resolved.is_file():
        return {
            "denied": True,
            "tool": "read_file",
            "reason": "file not found",
            "path": path,
        }
    return {"path": str(resolved), "content": resolved.read_text(encoding="utf-8")}


def run_tests_in_root(root: Path | None = None) -> dict:
    box = Path(root) if root is not None else SANDBOX
    box = box.resolve()
    test_file = box / "test_fixture.py"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-q",
            "--override-ini",
            "addopts=",
        ],
        cwd=str(box),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }


def make_sandbox_tools(root: Path) -> list:
    box = Path(root).resolve()

    @tool
    def read_file(path: str) -> dict:
        """Read a utf-8 file under the sandbox root."""
        return read_under_root(path, box)

    @tool
    def write_file(path: str, content: str) -> dict:
        """Write a utf-8 file. Paths that leave the sandbox root miss."""
        return write_under_root(path, content, box)

    @tool
    def run_tests() -> dict:
        """Run pytest on the sandbox folder only."""
        return run_tests_in_root(box)

    return [read_file, write_file, run_tests]


def _call_parts(call: Any) -> tuple[str, dict, str]:
    if isinstance(call, dict):
        name = str(call.get("name") or "")
        args = dict(call.get("args") or {})
        call_id = str(call.get("id") or "call")
        return name, args, call_id
    name = str(getattr(call, "name", "") or "")
    args = dict(getattr(call, "args", None) or {})
    call_id = str(getattr(call, "id", "") or "call")
    return name, args, call_id


def run_loop(
    task: str,
    model=None,
    root: Path | None = None,
    max_steps: int = DEFAULT_CAP,
) -> dict:
    """Run the coding loop with cwd locked to root and a step cap."""
    box = Path(root) if root is not None else SANDBOX
    box = box.resolve()
    tools = make_sandbox_tools(box)
    by_name = {t.name: t for t in tools}
    chat = model if model is not None else get_chat_model()
    bound = chat.bind_tools(tools)
    messages: list[Any] = [
        SystemMessage(content=SANDBOX_SYSTEM),
        HumanMessage(content=task),
    ]
    stopped = "cap"
    steps = 0
    prev = os.getcwd()
    try:
        os.chdir(box)
        for steps in range(1, int(max_steps) + 1):
            ai = bound.invoke(messages)
            messages.append(ai)
            calls = list(getattr(ai, "tool_calls", None) or [])
            if not calls:
                stopped = "done"
                break
            for call in calls:
                name, args, call_id = _call_parts(call)
                tool = by_name.get(name)
                if tool is None:
                    payload: Any = {
                        "denied": True,
                        "tool": name,
                        "reason": "unknown tool",
                    }
                else:
                    payload = tool.invoke(args)
                messages.append(
                    ToolMessage(
                        content=json.dumps(payload, ensure_ascii=True),
                        tool_call_id=call_id,
                        name=name,
                    )
                )
        else:
            stopped = "cap"
    finally:
        os.chdir(prev)
    if stopped == "cap":
        messages.append(AIMessage(content=STOPPED))
    return {
        "messages": messages,
        "stopped": stopped,
        "steps": steps,
        "root": str(box),
        "stopped_line": STOPPED if stopped == "cap" else "",
    }
