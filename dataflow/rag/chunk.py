"""Chunk the DataFlow knowledge base so a fact stays with its name.

A character cut is a measured default. A heading cut keeps the section
path on every piece. Orphans are chunks that start mid-list or mid-table
with no heading.
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


def chunk_recursive(
    docs: list[Document],
    chunk_size: int,
    chunk_overlap: int = 0,
) -> list[Document]:
    """Character cut. Size and overlap are arguments, not inherited constants."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_documents(docs)


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
        for piece in pieces:
            meta = dict(doc.metadata or {})
            meta.update(piece.metadata or {})
            path = heading_path(meta)
            if path:
                meta["heading_path"] = path
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
