"""FAISS index for the DataFlow knowledge base.

One embedder from config builds the index and queries it. A laptop
lab can stay on this file; pgvector is the production swap.

Every chunk gets a stable id (its source, heading path, csv row and its
position in the file), and every saved index gets index_meta.json beside it,
so a changed file can be found again and refreshed instead of rebuilding.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from config import ROOT, get_embeddings
from dataflow.rag.chunk import chunk_by_heading, chunk_recursive, heading_path
from dataflow.rag.load import list_knowledge_files, load_knowledge_base, relative_source
from dataflow.rag.manifest import diff, embedder_identity, file_hash, load_manifest, save_manifest

INDEX_DIR = ROOT / "dataflow" / "data" / "faiss_index"


def measured_dimension(embeddings: Any = None) -> int:
    """Embed one short string once. This is the column width."""
    embeddings = embeddings or get_embeddings()
    vector = embeddings.embed_query("dimension probe")
    return len(vector)


def _chunks_for(docs: list[Document], chunker: str) -> list[Document]:
    if chunker == "heading":
        return chunk_by_heading(docs)
    return chunk_recursive(docs, chunk_size=1000, chunk_overlap=0)


def chunk_id(chunk: Document, n: int) -> str:
    """A stable id: the same file, section, row and position give the same id on every build."""
    meta = chunk.metadata or {}
    row = meta.get("row")
    key = "\n".join(
        [
            str(meta.get("source") or ""),
            str(meta.get("heading_path") or ""),
            "" if row is None else str(row),
            str(n),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def chunks_with_ids(docs: list[Document], chunker: str = "heading") -> tuple[list[Document], list[str]]:
    """Chunk the documents and give each chunk its stable id (n counts the chunks of one source file)."""
    chunks = _chunks_for(docs, chunker)
    seen: Counter[str] = Counter()
    ids: list[str] = []
    for chunk in chunks:
        source = str((chunk.metadata or {}).get("source") or "")
        ids.append(chunk_id(chunk, seen[source]))
        seen[source] += 1
    return chunks, ids


def _source_path(source: str) -> Path:
    path = Path(source)
    return path if path.is_absolute() else ROOT / source


def _manifest_files(chunks: list[Document], ids: list[str]) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for chunk, cid in zip(chunks, ids):
        source = str((chunk.metadata or {}).get("source") or "")
        row = files.get(source)
        if row is None:
            path = _source_path(source)
            row = {"sha256": file_hash(path), "size": path.stat().st_size, "chunk_ids": []}
            files[source] = row
        row["chunk_ids"].append(cid)
    return files


def build_faiss_index(
    docs: list[Document] | None = None,
    chunker: str = "heading",
    index_dir: Path | str | None = INDEX_DIR,
    embeddings: Any = None,
) -> FAISS:
    """Build a FAISS index. Writes to index_dir, with index_meta.json beside it, when that path is set."""
    embeddings = embeddings or get_embeddings()
    if docs is None:
        docs = load_knowledge_base()
    chunks, ids = chunks_with_ids(docs, chunker)
    if not chunks:
        raise ValueError("no chunks to index")
    index = FAISS.from_documents(chunks, embeddings, ids=ids)
    if index_dir is not None:
        path = Path(index_dir)
        path.mkdir(parents=True, exist_ok=True)
        index.save_local(str(path))
        save_manifest(
            path,
            {
                "chunker": chunker,
                "embedder": embedder_identity(embeddings),
                "width": int(index.index.d),
                "count": int(index.index.ntotal),
                "files": _manifest_files(chunks, ids),
            },
        )
    return index


def check_index_embedder(index: FAISS, embeddings: Any) -> int:
    """Embed one probe and compare its width with the index's. A mismatch is a sentence, not faiss's bare assert."""
    width = measured_dimension(embeddings)
    built = int(index.index.d)
    if width != built:
        raise ValueError(
            f"the index was built {built} wide and this embedder returns {width}: "
            "rebuild the index with the embedder you query it with"
        )
    return width


def load_faiss_index(
    index_dir: Path | str = INDEX_DIR,
    embeddings: Any = None,
) -> FAISS:
    embeddings = embeddings or get_embeddings()
    index = FAISS.load_local(
        str(index_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    check_index_embedder(index, embeddings)
    return index


def current_files(roots) -> dict[str, Path]:
    """Repo-relative source to path, for every loadable file under the roots now."""
    return {relative_source(path): path for path in list_knowledge_files(roots)}


def refresh_index(index: FAISS, index_dir: Path | str, roots) -> dict[str, Any]:
    """Bring a saved index up to date with the files under roots, one file at a time.

    A changed or removed file's chunks are deleted by the ids its manifest row
    holds; an added or changed file is loaded, chunked and embedded again with
    stable ids. An unchanged file is never sent to the embedder. Saves the index
    and the manifest, and returns the diff and the number of texts embedded.
    """
    meta = load_manifest(index_dir)
    if meta is None:
        raise ValueError(f"no index_meta.json in {index_dir}; build the index first")
    paths = current_files(roots)
    changes = diff(meta, {source: file_hash(path) for source, path in paths.items()})
    files = dict(meta.get("files") or {})
    stale: list[str] = []
    for source in changes["changed"] + changes["removed"]:
        stale.extend(files.pop(source)["chunk_ids"])
    if stale:
        index.delete(ids=stale)
    embedded = 0
    for source in changes["added"] + changes["changed"]:
        docs = load_knowledge_base(roots=(paths[source],))
        chunks, ids = chunks_with_ids(docs, meta.get("chunker", "heading"))
        if chunks:
            index.add_documents(chunks, ids=ids)
            embedded += len(chunks)
            files.update(_manifest_files(chunks, ids))
    meta["files"] = files
    meta["count"] = int(index.index.ntotal)
    if any(changes.values()):
        index.save_local(str(index_dir))
        save_manifest(index_dir, meta)
    return {**changes, "embedded": embedded, "count": meta["count"]}


def _row_payload(doc: Document, score: float) -> dict:
    meta = dict(doc.metadata or {})
    path = heading_path(meta) or meta.get("heading_path") or ""
    return {
        "text": doc.page_content,
        "source": meta.get("source", ""),
        "folder": meta.get("folder"),
        "score": float(score),
        "row": meta.get("row"),
        "heading_path": path,
        "h2": meta.get("h2"),
        "h3": meta.get("h3"),
    }


def search(
    index: FAISS,
    question: str,
    k: int = 3,
    folder: str | None = None,
) -> list[dict]:
    """Nearest passages. Folder filter runs after fetch, then cut to k."""
    fetch = k if not folder else max(k * 10, 32)
    pairs = index.similarity_search_with_score(question, k=fetch)
    rows: list[dict] = []
    for doc, score in pairs:
        item = _row_payload(doc, score)
        if folder and item.get("folder") != folder:
            continue
        rows.append(item)
        if len(rows) >= k:
            break
    return rows


if __name__ == "__main__":
    built = build_faiss_index()
    width = measured_dimension()
    print("index_dir", INDEX_DIR.as_posix())
    print("dimension", width)
    print("built", type(built).__name__)
