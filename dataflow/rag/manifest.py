"""What an index on disk was built from, so it can be checked and refreshed.

index_meta.json sits beside index.faiss: the scope and folders, the chunker, the
embedder's class and model, the width and count, and per source file its size,
sha256 and the ids of its chunks. A file's hash is its bytes, never its mtime:
git checkout changes the mtime without changing a word.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

MANIFEST_NAME = "index_meta.json"


def file_hash(path: Path | str) -> str:
    """sha256 of the file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def embedder_identity(embeddings: Any) -> dict[str, Any]:
    """The embedder's class and model name, read off the object (no call)."""
    model = getattr(embeddings, "model", None) or getattr(embeddings, "model_name", None)
    return {"class": type(embeddings).__name__, "model": model}


def load_manifest(index_dir: Path | str) -> dict[str, Any] | None:
    path = Path(index_dir) / MANIFEST_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(index_dir: Path | str, meta: dict[str, Any]) -> Path:
    path = Path(index_dir) / MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def diff(meta: dict[str, Any], files: dict[str, str]) -> dict[str, list[str]]:
    """Compare the manifest's files with the files on disk now (source to sha256).

    added: on disk, not in the manifest. removed: in the manifest, not on disk.
    changed: in both, with a different hash. Each list is sorted.
    """
    indexed = {source: row["sha256"] for source, row in (meta.get("files") or {}).items()}
    added = sorted(source for source in files if source not in indexed)
    removed = sorted(source for source in indexed if source not in files)
    changed = sorted(source for source in files if source in indexed and files[source] != indexed[source])
    return {"added": added, "changed": changed, "removed": removed}
