"""Load the DataFlow knowledge base as documents with sources.

A loader matches the file type so a csv stays rows, a json file stays
records, and a markdown page keeps its path. The source set here is
the citation every later step depends on.

Office files (a PDF, a Word file) load only when asked, by suffixes=, so
the default load keeps its counts. A Word file keeps its headings through
their styles; a PDF keeps them through its bookmarks (its outline), since
the page text alone does not say which line is a heading.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from langchain_community.document_loaders import CSVLoader, TextLoader
from langchain_core.documents import Document

from config import ROOT

KB_DIR = ROOT / "dataflow" / "knowledge_base"
WIKI_DIR = ROOT / "dataflow" / "wiki"

TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
CSV_SUFFIXES = {".csv"}
JSON_SUFFIXES = {".json"}
LOADABLE = TEXT_SUFFIXES | CSV_SUFFIXES | JSON_SUFFIXES
PDF_SUFFIXES = {".pdf"}
WORD_SUFFIXES = {".docx"}
OFFICE_SUFFIXES = PDF_SUFFIXES | WORD_SUFFIXES

# Office files for lab 22.6, rendered from a customer-facing page. Outside the
# knowledge base and the wiki, so no default load and no index includes them.
DOCUMENTS_DIR = ROOT / "dataflow" / "documents"

KB_FOLDERS = {
    "business_data",
    "customer_facing",
    "internal_operations",
    "legal_compliance",
}


def list_knowledge_files(
    roots: Iterable[Path] = (KB_DIR, WIKI_DIR),
    *,
    suffixes: Iterable[str] = LOADABLE,
) -> list[Path]:
    """Return loadable files under the given roots, sorted."""
    wanted = {suffix.lower() for suffix in suffixes}
    files: list[Path] = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix.lower() in wanted:
                files.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in wanted:
                continue
            files.append(path)
    return files


def folder_for(path: Path) -> str:
    """First folder under knowledge_base, or wiki, or documents."""
    parts = path.resolve().parts
    if "wiki" in parts:
        return "wiki"
    if "documents" in parts and "dataflow" in parts:
        return "documents"
    if "knowledge_base" in parts:
        index = parts.index("knowledge_base")
        if index + 1 < len(parts) and parts[index + 1] in KB_FOLDERS:
            return parts[index + 1]
        if index + 1 < len(parts):
            return str(parts[index + 1])
    return "other"


def relative_source(path: Path) -> str:
    """Repo-relative path with forward slashes."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def _stamp(doc: Document, path: Path, extra: dict | None = None) -> Document:
    metadata = dict(doc.metadata or {})
    metadata["source"] = relative_source(path)
    metadata["folder"] = folder_for(path)
    if extra:
        metadata.update(extra)
    doc.metadata = metadata
    return doc


def load_json(path: Path | str) -> list[Document]:
    """Hand-written json loader. JSONLoader needs jq, which Windows lacks."""
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: list[object]
    if isinstance(payload, list):
        records = list(payload)
    elif isinstance(payload, dict):
        lists = [v for v in payload.values() if isinstance(v, list)]
        if lists:
            records = max(lists, key=len)
        else:
            records = [payload]
    else:
        records = [payload]
    docs: list[Document] = []
    for index, record in enumerate(records):
        text = json.dumps(record, indent=2, ensure_ascii=True)
        docs.append(
            _stamp(
                Document(page_content=text, metadata={}),
                path,
                extra={"record": index},
            )
        )
    return docs


def _section(lines: list[str], heads: dict[str, str], path: Path, extra: dict | None = None) -> Document:
    from dataflow.rag.chunk import heading_path

    meta = dict(heads)
    if heading_path(meta):
        meta["heading_path"] = heading_path(meta)
    return _stamp(Document(page_content="\n".join(lines), metadata=meta), path, extra=extra)


def load_docx(path: Path | str) -> list[Document]:
    """A Word file as one document per section: a paragraph in a Heading 1 to 3 style starts a new section.

    Each document carries h1 to h3 and heading_path from the headings above it,
    so a Word section cites the way a markdown section does.
    """
    from docx import Document as WordFile

    path = Path(path)
    docs: list[Document] = []
    heads: dict[str, str] = {}
    lines: list[str] = []
    for para in WordFile(str(path)).paragraphs:
        style = para.style.name if para.style is not None else ""
        level = int(style.split()[-1]) if style.startswith("Heading ") and style.split()[-1].isdigit() else 0
        if 1 <= level <= 3:
            if lines:
                docs.append(_section(lines, heads, path))
            heads = {key: value for key, value in heads.items() if int(key[1]) < level}
            heads[f"h{level}"] = para.text.strip()
            lines = []
        elif para.text.strip():
            lines.append(para.text.strip())
    if lines:
        docs.append(_section(lines, heads, path))
    return docs


def _outline(reader) -> list[tuple[int, str, int]]:
    """A PDF's bookmarks as (level, title, page index), in reading order."""
    entries: list[tuple[int, str, int]] = []

    def walk(items, level: int) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
            else:
                entries.append((level, str(item.title).strip(), reader.get_destination_page_number(item)))

    walk(reader.outline, 1)
    return entries


def load_pdf(path: Path | str) -> list[Document]:
    """A PDF as one document per bookmarked section, or one per page when it has no bookmarks.

    pypdf reads the page text; the outline says where each heading starts and
    how deep it sits, so each section gets h1 to h3, heading_path, and the page
    its heading is on.
    """
    from pypdf import PdfReader

    path = Path(path)
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    entries = _outline(reader)
    if not entries:
        return [
            _stamp(Document(page_content=text, metadata={}), path, extra={"page": n})
            for n, text in enumerate(pages, start=1)
        ]
    lines = [(n, line.strip()) for n, text in enumerate(pages, start=1) for line in text.splitlines() if line.strip()]
    docs: list[Document] = []
    heads: dict[str, str] = {}
    cursor = 0
    starts: list[tuple[int, int, str]] = []
    for level, title, _ in entries:
        at = next((i for i in range(cursor, len(lines)) if lines[i][1] == title), None)
        if at is None:
            continue
        starts.append((at, level, title))
        cursor = at + 1
    for index, (at, level, title) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(lines)
        heads = {key: value for key, value in heads.items() if int(key[1]) < level}
        heads[f"h{level}"] = title
        body = [text for _, text in lines[at + 1:end]]
        if body:
            docs.append(_section(body, heads, path, extra={"page": lines[at][0]}))
    return docs


def _load_one(path: Path) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        loaded = TextLoader(str(path), encoding="utf-8").load()
        return [_stamp(doc, path) for doc in loaded]
    if suffix in CSV_SUFFIXES:
        loaded = CSVLoader(str(path), encoding="utf-8").load()
        return [_stamp(doc, path) for doc in loaded]
    if suffix in JSON_SUFFIXES:
        return load_json(path)
    if suffix in PDF_SUFFIXES:
        return load_pdf(path)
    if suffix in WORD_SUFFIXES:
        return load_docx(path)
    return []


def load_knowledge_base(
    roots: Iterable[Path] = (KB_DIR, WIKI_DIR),
    *,
    suffixes: Iterable[str] = LOADABLE,
) -> list[Document]:
    """Walk the knowledge base and the wiki. One call, every file.

    suffixes picks the file types; the default leaves PDF and Word files out.
    """
    docs: list[Document] = []
    for path in list_knowledge_files(roots, suffixes=suffixes):
        docs.extend(_load_one(path))
    return docs


def load_customer_facing() -> list[Document]:
    """Wiki plus customer_facing. The retrieve tool's default scope."""
    return load_knowledge_base(roots=(KB_DIR / "customer_facing", WIKI_DIR))
