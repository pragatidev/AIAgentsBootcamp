"""Document tools over the DataFlow knowledge base. No model."""

from __future__ import annotations

from pathlib import Path

from langchain.tools import tool

from dataflow.tools.policy import search_policy

REPO = Path(__file__).resolve().parents[1]
DATAFLOW = REPO / "dataflow"
KNOWLEDGE_BASE = DATAFLOW / "knowledge_base"
WIKI = DATAFLOW / "wiki"
TICKETS = DATAFLOW / "data" / "tickets.jsonl"
READ_CAP = 6000
CUT_NOTE = "\n\n[truncated to 6000 characters]"


def _all_document_paths() -> list[Path]:
    """Knowledge base files, wiki files, and the tickets jsonl."""
    paths: list[Path] = []
    if KNOWLEDGE_BASE.is_dir():
        for path in sorted(KNOWLEDGE_BASE.rglob("*")):
            if path.is_file():
                paths.append(path)
    if WIKI.is_dir():
        for path in sorted(WIKI.iterdir()):
            if path.is_file():
                paths.append(path)
    if TICKETS.is_file():
        paths.append(TICKETS)
    return paths


def document_names() -> list[str]:
    """Relative posix names under dataflow/."""
    names: list[str] = []
    for path in _all_document_paths():
        names.append(path.relative_to(DATAFLOW).as_posix())
    return names


def _resolve_document(name: str) -> Path | str:
    raw = (name or "").strip().replace("\\", "/")
    if not raw:
        return "not found: empty name"
    paths = _all_document_paths()
    exact: list[Path] = []
    base: list[Path] = []
    suffix: list[Path] = []
    for path in paths:
        rel = path.relative_to(DATAFLOW).as_posix()
        if raw == rel or raw == "/" + rel:
            exact.append(path)
        if path.name == raw or path.name == Path(raw).name:
            base.append(path)
        if rel.endswith(raw.lstrip("/")):
            suffix.append(path)
    if len(exact) == 1:
        return exact[0]
    if len(suffix) == 1:
        return suffix[0]
    if len(base) == 1:
        return base[0]
    if len(base) > 1:
        rels = [p.relative_to(DATAFLOW).as_posix() for p in base]
        return "ambiguous name " + raw + ": " + ", ".join(rels)
    return "not found: " + raw


@tool
def list_documents() -> list[str]:
    """List DataFlow knowledge base files, wiki files, and the tickets file.

    Names are relative to the dataflow/ folder, posix style.
    """
    return document_names()


@tool
def read_document(name: str) -> str:
    """Read one DataFlow document by file name or relative path.

    Returns the text. Caps at 6000 characters and adds a note when cut.
    """
    resolved = _resolve_document(name)
    if isinstance(resolved, str):
        return resolved
    text = resolved.read_text(encoding="utf-8", errors="replace")
    if len(text) > READ_CAP:
        return text[:READ_CAP] + CUT_NOTE
    return text


__all__ = [
    "list_documents",
    "read_document",
    "search_policy",
    "document_names",
]
