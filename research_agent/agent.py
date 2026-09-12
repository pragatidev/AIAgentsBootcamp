"""Build the DataFlow research and report deep agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, StateBackend
from langchain.agents.middleware import TodoListMiddleware

from config import get_chat_model
from research_agent.tools import list_documents, read_document, search_policy

PACKAGE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = PACKAGE_DIR / "reports"

RESEARCH_TOOLS = [list_documents, read_document, search_policy]

READER_SYSTEM = (
    "You read one DataFlow document. Return the return-complaint or refund "
    "themes you find, with short quotes and the file name. If the file is not "
    "about returns, shipping, or refunds, say so in one line. Do not write files."
)

DEFAULT_SUBAGENTS = [
    {
        "name": "reader",
        "description": (
            "Reads one document and returns the return-complaint themes "
            "with quotes and the file name"
        ),
        "system_prompt": READER_SYSTEM,
        "tools": [read_document],
    }
]

RESEARCH_SYSTEM = """You research DataFlow customer complaints and write a short report with sources.

Do this in order. Do not skip step 1.

1. Call write_todos first with a short plan. Include: list documents, read the useful ones, note themes, draft the report, add sources.
2. Call list_documents. Call search_policy for the policy lines that apply.
3. For each useful document, call the reader subagent through the task tool, one document at a time. Pass the file name. Do not paste whole files into this conversation.
4. Keep running notes in /notes.md with write_file.
5. Write the final report with write_file:
   - /reports/return_complaints.md when the question is about returns or refunds
   - /reports/shipping_delays.md when the question is about shipping delays
   - /reports/report.md for any other question
   The report must have a Sources section that lists file names you actually read.
6. Stop. Tell the user the report path and what you could not find.

Paths are virtual and start with /. Use write_file, read_file, and ls. A short report with two or three themes and real file names is a complete job. Do not keep calling tools after the report is written.
"""


def make_real_backend(root: str | Path | None = None) -> FilesystemBackend:
    """FilesystemBackend rooted so /reports/... lands under research_agent/reports/."""
    path = Path(root) if root is not None else PACKAGE_DIR
    path.mkdir(parents=True, exist_ok=True)
    (path / "reports").mkdir(parents=True, exist_ok=True)
    return FilesystemBackend(root_dir=path, virtual_mode=True)


def find_report_files(root: str | Path | None = None) -> list[Path]:
    """Markdown reports on disk, excluding the committed sample."""
    reports = (Path(root) if root is not None else PACKAGE_DIR) / "reports"
    if not reports.is_dir():
        return []
    skip = {"sample_return_complaints.md"}
    found: list[Path] = []
    for path in sorted(reports.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.name in skip:
            continue
        found.append(path)
    return found


def files_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    files = state.get("files") or {}
    return files if isinstance(files, dict) else {}


def report_from_state(state: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """Return (path, text) for the first report-like virtual file."""
    files = files_from_state(state)
    preferred = (
        "/reports/return_complaints.md",
        "/reports/shipping_delays.md",
        "/reports/report.md",
        "reports/return_complaints.md",
    )
    for key in preferred:
        if key in files:
            return key, _file_text(files[key])
    for key, data in files.items():
        name = str(key).replace("\\", "/")
        if name.rstrip("/").endswith(".md") and "conversation_history" not in name:
            if "notes.md" in name:
                continue
            return key, _file_text(data)
    return None, None


def _file_text(data: Any) -> str:
    if isinstance(data, dict):
        return str(data.get("content") or "")
    return str(data or "")


def build_research_agent(
    model: Any = None,
    backend: Any = None,
    subagents: list[dict[str, Any]] | None = None,
):
    """Compiled deep agent: plan, files, isolated reader subagent."""
    chosen_backend = backend if backend is not None else StateBackend()
    return create_deep_agent(
        model=model or get_chat_model(),
        tools=RESEARCH_TOOLS,
        system_prompt=RESEARCH_SYSTEM,
        subagents=subagents or DEFAULT_SUBAGENTS,
        backend=chosen_backend,
        middleware=[TodoListMiddleware()],
    )
