"""Load the DataFlow knowledge base as documents with sources.

A loader matches the file type so a csv stays rows, a json file stays
records, and a markdown page keeps its path. The source set here is
the citation every later step depends on.
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

KB_FOLDERS = {
    "business_data",
    "customer_facing",
    "internal_operations",
    "legal_compliance",
}


def list_knowledge_files(
    roots: Iterable[Path] = (KB_DIR, WIKI_DIR),
) -> list[Path]:
    """Return loadable files under the given roots, sorted."""
    files: list[Path] = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix.lower() in LOADABLE:
                files.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in LOADABLE:
                continue
            files.append(path)
    return files


def folder_for(path: Path) -> str:
    """First folder under knowledge_base, or wiki."""
    parts = path.resolve().parts
    if "wiki" in parts:
        return "wiki"
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
    return []


def load_knowledge_base(
    roots: Iterable[Path] = (KB_DIR, WIKI_DIR),
) -> list[Document]:
    """Walk the knowledge base and the wiki. One call, every file."""
    docs: list[Document] = []
    for path in list_knowledge_files(roots):
        docs.extend(_load_one(path))
    return docs


def load_customer_facing() -> list[Document]:
    """Wiki plus customer_facing. The retrieve tool's default scope."""
    return load_knowledge_base(roots=(KB_DIR / "customer_facing", WIKI_DIR))
