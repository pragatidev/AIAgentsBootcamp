"""Chunk the DataFlow knowledge base so a fact stays with its name.

A character cut is a measured default. A heading cut keeps the section
path on every piece. Orphans are chunks that start mid-list or mid-table
with no heading.

A chunk of a text file also records where it came from: start_index (the
character offset in the file) and line_start and line_end (1-based), so a
citation can open the file at the lines. The chunk's text never changes.
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

HEADER_SPLIT = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


TEXT_SOURCE_SUFFIXES = (".md", ".markdown", ".txt")


def line_span(source_text: str, start: int, length: int) -> tuple[int, int]:
    """The 1-based first and last line of the text that starts at offset start and runs length characters."""
    line_start = source_text.count("\n", 0, start) + 1
    line_end = source_text.count("\n", 0, start + max(length, 1) - 1) + 1
    return line_start, line_end


def _is_text_source(source: str) -> bool:
    return (source or "").replace("\\", "/").lower().endswith(TEXT_SOURCE_SUFFIXES)


def _stamp_span(meta: dict, source_text: str, start: int, length: int) -> None:
    line_start, line_end = line_span(source_text, start, length)
    meta["start_index"] = start
    meta["line_start"] = line_start
    meta["line_end"] = line_end


def chunk_recursive(
    docs: list[Document],
    chunk_size: int,
    chunk_overlap: int = 0,
) -> list[Document]:
    """Character cut. Size and overlap are arguments, not inherited constants."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    out: list[Document] = []
    for doc in docs:
        text_file = _is_text_source(str((doc.metadata or {}).get("source") or ""))
        for chunk in splitter.split_documents([doc]):
            meta = dict(chunk.metadata or {})
            start = meta.pop("start_index", None)
            if text_file and start is not None and start >= 0:
                _stamp_span(meta, doc.page_content, start, len(chunk.page_content))
            chunk.metadata = meta
            out.append(chunk)
    return out


def _piece_span(source_lines: list[str], piece: Document, cursor: int) -> tuple[int, int] | None:
    """Line numbers (0-based, inclusive) of a heading piece in its file, searching forward from cursor.

    The splitter drops blank lines and leading spaces, so lines are matched stripped.
    The span opens on the piece's own heading line when there is one.
    """
    wanted = [line.strip() for line in piece.page_content.splitlines() if line.strip()]
    if not wanted:
        return None
    stripped = [line.strip() for line in source_lines]
    try:
        first = stripped.index(wanted[0], cursor)
        last = first
        for line in wanted[1:]:
            last = stripped.index(line, last + 1)
    except ValueError:
        return None
    meta = piece.metadata or {}
    header = next((meta[key] for key in ("h3", "h2", "h1") if meta.get(key)), None)
    for back in range(first - 1, max(cursor, first - 6) - 1, -1):
        line = stripped[back]
        if line.startswith("#") and line.lstrip("#").strip() == str(header or "").strip():
            first = back
            break
        if line:
            break
    return first, last


def heading_path(metadata: dict) -> str:
    """Join h2 > h3 (or h1 when those are missing) for the chunk's first line."""
    parts: list[str] = []
    for key in ("h2", "h3"):
        value = metadata.get(key)
        if value:
            parts.append(str(value).strip())
    if not parts and metadata.get("h1"):
        parts.append(str(metadata["h1"]).strip())
    return " > ".join(parts)


def _is_markdown_source(source: str) -> bool:
    lower = (source or "").replace("\\", "/").lower()
    return lower.endswith(".md") or lower.endswith(".markdown")


def chunk_by_heading(docs: list[Document]) -> list[Document]:
    """Heading cut for markdown. Recursive fallback for the rest.

    Prepends the heading path as the first line of each chunk so the
    embedder sees the section name with the fact.
    """
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADER_SPLIT,
        strip_headers=True,
    )
    out: list[Document] = []
    for doc in docs:
        source = str((doc.metadata or {}).get("source") or "")
        if not _is_markdown_source(source):
            out.extend(chunk_recursive([doc], chunk_size=1000, chunk_overlap=0))
            continue
        pieces = splitter.split_text(doc.page_content)
        source_lines = doc.page_content.split("\n")
        offsets = [0]
        for line in source_lines:
            offsets.append(offsets[-1] + len(line) + 1)
        cursor = 0
        for piece in pieces:
            meta = dict(doc.metadata or {})
            meta.update(piece.metadata or {})
            path = heading_path(meta)
            if path:
                meta["heading_path"] = path
            span = _piece_span(source_lines, piece, cursor)
            if span is not None:
                first, last = span
                start = offsets[first]
                _stamp_span(meta, doc.page_content, start, offsets[last] + len(source_lines[last]) - start)
                cursor = last + 1
            text = piece.page_content
            if path and not text.startswith(path):
                text = path + "\n" + text
            out.append(Document(page_content=text, metadata=meta))
    return out


def orphan_count(chunks: list) -> int:
    """Chunks whose first line starts mid-list or mid-table with no heading.

    A hanging bullet or table row starts with '-' or '|'. A numbered
    table row can start with a digit. A heading path line (h2 > h3) or
    any '#' in the chunk means the name survived.
    """
    count = 0
    for chunk in chunks:
        text = chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        lines = text.splitlines()
        if not lines:
            continue
        first = lines[0].lstrip()
        if first.startswith("-") or first.startswith("|"):
            if "#" not in text:
                count += 1
            continue
        if "#" in text:
            continue
        if " > " in lines[0]:
            continue
        if first[:1].isdigit() and "|" in first:
            count += 1
    return count
