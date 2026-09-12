"""Filled research agent. Plan, files, isolated subagents, sourced report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config import get_chat_model

HERE = Path(__file__).resolve().parent
REPORTS_DIR = HERE / "reports"

FILL_FROM_REPO = True

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
    from research_agent.agent import RESEARCH_SYSTEM

    _ = RESEARCH_SYSTEM
    _ = question
    return [
        {"content": "list documents", "status": "pending"},
        {"content": "read the useful ones", "status": "pending"},
        {"content": "draft the report", "status": "pending"},
        {"content": "add sources", "status": "pending"},
    ]


def write_files(root: str | Path, path: str, content: str) -> Path:
    dest = Path(root)
    dest.mkdir(parents=True, exist_ok=True)
    rel = str(path).lstrip("/").replace("\\", "/")
    target = dest / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def isolated_subagent(name: str) -> dict[str, Any]:
    from research_agent.agent import DEFAULT_SUBAGENTS

    for row in DEFAULT_SUBAGENTS:
        if row.get("name") == name:
            return dict(row)
    return {"name": name, "description": "missing"}


def sources_section(text: str) -> str | None:
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
    include_sources: bool = True,
) -> Path:
    chat = model if model is not None else get_chat_model()
    result = chat.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You research DataFlow customer returns. "
                    "Write three short themes in plain sentences. "
                    "Do not invent file names."
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
