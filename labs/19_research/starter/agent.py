"""Research and report starter. Plan, files, and isolated subagents are TODO stubs.

write_report calls the model from config, then writes a report with no
Sources section. That is the planted miss. The solution adds sources.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config import get_chat_model

HERE = Path(__file__).resolve().parent
REPORTS_DIR = HERE / "reports"

FILL_FROM_REPO = False  # TODO fill: import and delegate from the finished package

SOURCE_PATHS = (
    "dataflow/wiki/return_policy.md",
    "dataflow/data/tickets.jsonl",
)


def _content(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "\n".join(part for part in parts if part).strip()
    return str(content or "").strip()


def plan(question: str) -> list[dict[str, str]]:
    """TODO plan: store a short todo list for the research job."""
    if not FILL_FROM_REPO:
        raise NotImplementedError("store a short todo list for the research job")
    from research_agent.agent import RESEARCH_SYSTEM

    _ = RESEARCH_SYSTEM
    return [
        {"content": "list documents", "status": "pending"},
        {"content": "read the useful ones", "status": "pending"},
        {"content": "draft the report", "status": "pending"},
        {"content": "add sources", "status": "pending"},
    ]


def write_files(root: str | Path, path: str, content: str) -> Path:
    """TODO files: write a note or report through the filesystem backend."""
    if not FILL_FROM_REPO:
        raise NotImplementedError("write a note or report through the filesystem backend")
    dest = Path(root)
    dest.mkdir(parents=True, exist_ok=True)
    rel = str(path).lstrip("/").replace("\\", "/")
    target = dest / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def isolated_subagent(name: str) -> dict[str, Any]:
    """TODO isolated subagents: run a reader with a clean context."""
    if not FILL_FROM_REPO:
        raise NotImplementedError("run a reader with a clean context")
    from research_agent.agent import DEFAULT_SUBAGENTS

    for row in DEFAULT_SUBAGENTS:
        if row.get("name") == name:
            return dict(row)
    return {"name": name, "description": "missing"}


def sources_section(text: str) -> str | None:
    """Return the Sources section, or None if it is missing."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("#").strip()
        if stripped.lower() == "sources":
            start = i
            break
    if start is None:
        return None
    block = "\n".join(lines[start:])
    return block if block.strip() else None


def report_has_sources(text: str) -> bool:
    """True when a Sources section exists and names a path."""
    section = sources_section(text)
    if not section:
        return False
    normalized = section.replace("\\", "/")
    tokens = (".md", ".jsonl", "dataflow/", "wiki/")
    return any(token in normalized for token in tokens)


def write_report(
    question: str,
    dest: str | Path | None = None,
    *,
    model: Any = None,
    include_sources: bool = False,
) -> Path:
    """Call the model from config and write a short report.

    The starter plant keeps include_sources=False, so the file has no
    Sources section. The solution writes sources.
    """
    chat = model if model is not None else get_chat_model()
    result = chat.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You research DataFlow customer returns. "
                    "Write three short themes in plain sentences. "
                    "Do not invent file names. Do not write a Sources section."
                ),
            },
            {"role": "user", "content": question},
        ]
    )
    themes = _content(result) or "The model returned an empty theme list."
    body = "# Report\n\n" + themes.strip() + "\n"
    if include_sources:
        body = (
            body
            + "\n## Sources\n\n"
            + "\n".join("- " + path for path in SOURCE_PATHS)
            + "\n"
        )
    target = Path(dest) if dest is not None else REPORTS_DIR / "report.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target
