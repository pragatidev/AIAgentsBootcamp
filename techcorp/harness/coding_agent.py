"""A small create_agent coding desk. Permissions live in a dict, not a prompt.

The planted variant drops the shell permission line so the check falls
through to allow. Lab 15.2.2 shows that miss, then the typed denial.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.tools import tool

from config import get_chat_model

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_PATH = Path(__file__).resolve().parent / "AGENTS.md"
SANDBOX_REL = "techcorp/harness/sandbox"
SANDBOX_ROOT = (REPO_ROOT / SANDBOX_REL).resolve()

PERMISSIONS: dict[str, dict[str, Any]] = {
    "read_file": {"allow": True},
    "write_file": {"root": SANDBOX_REL},
    "run_tests": {"allow": True},
    "shell": {"allow_commands": ["pytest"]},
}


def load_agents_md() -> str:
    return AGENTS_PATH.read_text(encoding="utf-8")


def check_permission(
    tool_name: str,
    table: dict[str, dict[str, Any]],
    *,
    command: str = "",
    path: str = "",
    fall_through: bool = False,
) -> dict | None:
    """Return a typed miss or None if the call may run."""
    spec = table.get(tool_name)
    if spec is None:
        if fall_through:
            # PLANTED: a missing permission line still runs the tool.
            # Lab 15.2.2 break. The committed table includes shell.
            return None
        return {
            "denied": True,
            "tool": tool_name,
            "reason": "no permission line",
        }
    if tool_name == "shell":
        cmd = (command or "").strip()
        first = cmd.split()[0] if cmd else ""
        allowed = list(spec.get("allow_commands") or [])
        ok = first in allowed or cmd.startswith("pytest") or cmd.startswith(
            "python -m pytest"
        )
        if not ok:
            return {
                "denied": True,
                "tool": "shell",
                "reason": "command not allowed",
            }
    if tool_name == "write_file":
        resolved = resolve_write_path(path)
        if isinstance(resolved, dict):
            return resolved
    return None


def resolve_write_path(path: str) -> Path | dict:
    """Accept notes.md or techcorp/harness/sandbox/notes.md. Leave the sandbox and miss."""
    raw = Path(path)
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        from_repo = (REPO_ROOT / raw).resolve()
        try:
            from_repo.relative_to(SANDBOX_ROOT)
            candidate = from_repo
        except ValueError:
            candidate = (SANDBOX_ROOT / raw).resolve()
    try:
        candidate.relative_to(SANDBOX_ROOT)
    except ValueError:
        return {
            "denied": True,
            "tool": "write_file",
            "reason": "path is outside the sandbox root",
            "path": path,
        }
    return candidate


def _read(path: str) -> dict:
    raw = Path(path)
    target = raw if raw.is_absolute() else (REPO_ROOT / raw)
    if not target.is_file():
        sandbox_try = SANDBOX_ROOT / raw
        if sandbox_try.is_file():
            target = sandbox_try
        else:
            return {
                "denied": True,
                "tool": "read_file",
                "reason": "file not found",
                "path": path,
            }
    return {"path": str(target), "content": target.read_text(encoding="utf-8")}


def _write(path: str, content: str) -> dict:
    resolved = resolve_write_path(path)
    if isinstance(resolved, dict):
        return resolved
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return {"path": str(resolved), "wrote": True, "chars": len(content)}


def _run_tests() -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(SANDBOX_ROOT / "test_fixture.py"),
            "-q",
            "--override-ini",
            "addopts=",
        ],
        cwd=str(SANDBOX_ROOT),
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


def _shell(command: str) -> dict:
    proc = subprocess.run(
        command,
        shell=True,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def make_tools(
    table: dict[str, dict[str, Any]] | None = None,
    *,
    fall_through: bool = False,
) -> list:
    """Build the four tools bound to one permission table."""
    perms = dict(table) if table is not None else dict(PERMISSIONS)

    @tool
    def read_file(path: str) -> dict:
        """Read a utf-8 text file and return its contents."""
        miss = check_permission(
            "read_file", perms, path=path, fall_through=fall_through
        )
        if miss:
            return miss
        return _read(path)

    @tool
    def write_file(path: str, content: str) -> dict:
        """Write a utf-8 text file. Only paths under techcorp/harness/sandbox/ are allowed."""
        miss = check_permission(
            "write_file",
            perms,
            path=path,
            fall_through=fall_through,
        )
        if miss:
            return miss
        return _write(path, content)

    @tool
    def run_tests() -> dict:
        """Run pytest on techcorp/harness/sandbox/test_fixture.py only."""
        miss = check_permission(
            "run_tests", perms, fall_through=fall_through
        )
        if miss:
            return miss
        return _run_tests()

    @tool
    def shell(command: str) -> dict:
        """Run a shell command. Only the pytest command is allowed."""
        miss = check_permission(
            "shell",
            perms,
            command=command,
            fall_through=fall_through,
        )
        if miss:
            return miss
        return _shell(command)

    return [read_file, write_file, run_tests, shell]


def planted_shell_table() -> dict[str, dict[str, Any]]:
    """PLANTED: shell permission line missing. Lab 15.2.2 break."""
    return {k: v for k, v in PERMISSIONS.items() if k != "shell"}


def build_coding_desk(model=None, *, plant_missing_shell: bool = False):
    """create_agent desk with the four tools and the permission table."""
    chat = model if model is not None else get_chat_model()
    if plant_missing_shell:
        tools = make_tools(planted_shell_table(), fall_through=True)
    else:
        tools = make_tools(PERMISSIONS, fall_through=False)
    return create_agent(
        model=chat,
        tools=tools,
        system_prompt=load_agents_md(),
        middleware=[ToolCallLimitMiddleware(run_limit=6)],
    )
