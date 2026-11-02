"""Index plumbing (23.2, 23.8): stable chunk ids, index_meta.json, refresh one changed file, one index per scope.

A hashing embedder that counts its calls stands in for the real one, here only. No Ollama.
"""

import importlib
import json
import os
import shutil
from pathlib import Path

import pytest

import config
from dataflow.rag.faiss_index import build_faiss_index, chunks_with_ids, load_faiss_index, refresh_index, search
from dataflow.rag.load import WIKI_DIR, load_knowledge_base
from dataflow.rag.manifest import diff, load_manifest
from tests.fixtures.hashing_embeddings import HashingEmbeddings

retrieve = importlib.import_module("dataflow.tools.retrieve")

NEW_LINE = "Express shipping now arrives in one business day inside the country."


class CountingEmbeddings(HashingEmbeddings):
    def __init__(self) -> None:
        super().__init__()
        self.texts = 0

    def embed_documents(self, texts):
        self.texts += len(texts)
        return super().embed_documents(texts)


@pytest.fixture
def wiki(tmp_path):
    copy = tmp_path / "wiki"
    shutil.copytree(WIKI_DIR, copy)
    return copy


def _build(wiki, tmp_path, emb):
    index_dir = tmp_path / "index"
    index = build_faiss_index(docs=load_knowledge_base(roots=(wiki,)), index_dir=index_dir, embeddings=emb)
    return index, index_dir


def _texts(index):
    return [doc.page_content for doc in index.docstore._dict.values()]


def test_ids_are_stable_across_builds():
    docs = load_knowledge_base(roots=(WIKI_DIR,))
    _, first = chunks_with_ids(docs)
    _, second = chunks_with_ids(load_knowledge_base(roots=(WIKI_DIR,)))
    assert first == second
    assert len(set(first)) == len(first)


def test_build_writes_a_manifest(wiki, tmp_path):
    emb = CountingEmbeddings()
    index, index_dir = _build(wiki, tmp_path, emb)
    meta = load_manifest(index_dir)
    assert meta["chunker"] == "heading"
    assert meta["embedder"] == {"class": "CountingEmbeddings", "model": None}
    assert meta["width"] == 256 and meta["count"] == index.index.ntotal
    assert sorted(Path(source).name for source in meta["files"]) == ["return_policy.md", "security.md", "shipping.md"]
    ids = [cid for row in meta["files"].values() for cid in row["chunk_ids"]]
    assert sorted(ids) == sorted(index.index_to_docstore_id.values())


def test_unchanged_refresh_embeds_nothing(wiki, tmp_path):
    emb = CountingEmbeddings()
    index, index_dir = _build(wiki, tmp_path, emb)
    emb.texts = 0
    result = refresh_index(index, index_dir, (wiki,))
    assert result["embedded"] == 0 and emb.texts == 0
    assert result["added"] == result["changed"] == result["removed"] == []


def test_changed_file_replaces_its_chunks(wiki, tmp_path):
    emb = CountingEmbeddings()
    index, index_dir = _build(wiki, tmp_path, emb)
    before = index.index.ntotal
    page = wiki / "shipping.md"
    old = page.read_text(encoding="utf-8")
    page.write_text(old.rstrip("\n") + "\n\n" + NEW_LINE + "\n", encoding="utf-8")
    emb.texts = 0
    result = refresh_index(index, index_dir, (wiki,))
    assert [Path(s).name for s in result["changed"]] == ["shipping.md"]
    assert result["embedded"] == emb.texts > 0
    texts = _texts(index)
    assert sum(NEW_LINE in text for text in texts) == 1
    assert index.index.ntotal == before
    reloaded = load_faiss_index(index_dir, embeddings=emb)
    hits = search(reloaded, NEW_LINE, k=1)
    assert NEW_LINE in hits[0]["text"]
    ids = list(reloaded.index_to_docstore_id.values())
    assert len(ids) == len(set(ids))


def test_removed_file_disappears(wiki, tmp_path):
    index, index_dir = _build(wiki, tmp_path, CountingEmbeddings())
    (wiki / "security.md").unlink()
    result = refresh_index(index, index_dir, (wiki,))
    assert [Path(s).name for s in result["removed"]] == ["security.md"]
    assert not any("security.md" in str(doc.metadata.get("source")) for doc in index.docstore._dict.values())
    assert all("security.md" not in source for source in load_manifest(index_dir)["files"])


def test_touch_without_edit_is_not_a_change(wiki, tmp_path):
    index, index_dir = _build(wiki, tmp_path, CountingEmbeddings())
    page = wiki / "return_policy.md"
    stat = page.stat()
    os.utime(page, (stat.st_atime + 120, stat.st_mtime + 120))
    meta = load_manifest(index_dir)
    from dataflow.rag.manifest import file_hash

    files = {source: file_hash(Path(source)) for source in meta["files"]}
    assert diff(meta, files) == {"added": [], "changed": [], "removed": []}


def test_diff_known_answer():
    meta = {"files": {"a.md": {"sha256": "1"}, "b.md": {"sha256": "2"}, "c.md": {"sha256": "3"}}}
    assert diff(meta, {"a.md": "1", "b.md": "9", "d.md": "4"}) == {"added": ["d.md"], "changed": ["b.md"], "removed": ["c.md"]}


@pytest.fixture
def scope_dirs(tmp_path, monkeypatch):
    emb = CountingEmbeddings()
    monkeypatch.setattr(config, "get_embeddings", lambda: emb)
    monkeypatch.setattr(retrieve, "SCOPE_DIRS", {"customer": tmp_path / "customer", "all": tmp_path / "all"})
    retrieve.reset_index()
    yield emb
    retrieve.reset_index()


def test_customer_index_holds_no_internal_folder(scope_dirs):
    index = retrieve.get_index(scope="customer")
    folders = {doc.metadata.get("folder") for doc in index.docstore._dict.values()}
    assert folders == {"wiki", "customer_facing"}


def test_get_index_rebuilds_when_the_manifest_differs(scope_dirs, capsys):
    retrieve.get_index(scope="customer")
    assert "rebuilding_index customer no index on disk yet" in capsys.readouterr().out
    retrieve.reset_index()
    retrieve.get_index(scope="customer")
    assert "rebuilding_index" not in capsys.readouterr().out
    meta_path = retrieve.SCOPE_DIRS["customer"] / "index_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["embedder"] = {"class": "OpenAIEmbeddings", "model": "another-embedder"}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    retrieve.reset_index()
    retrieve.get_index(scope="customer")
    assert "rebuilding_index customer the index on disk was built by another embedder" in capsys.readouterr().out
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["roots"] = ["dataflow/knowledge_base/customer_facing", "dataflow/knowledge_base/business_data", "dataflow/wiki"]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    retrieve.reset_index()
    retrieve.get_index(scope="customer")
    assert "rebuilding_index customer the index on disk was built from other folders" in capsys.readouterr().out


def test_an_old_index_with_no_manifest_rebuilds_once(scope_dirs, capsys):
    index_dir = retrieve.SCOPE_DIRS["customer"]
    build_faiss_index(docs=load_knowledge_base(roots=(WIKI_DIR,)), index_dir=index_dir, embeddings=scope_dirs)
    (index_dir / "index_meta.json").unlink()
    retrieve.get_index(scope="customer")
    assert "no index_meta.json" in capsys.readouterr().out
    assert (index_dir / "index_meta.json").is_file()


def test_a_width_mismatch_is_a_sentence(tmp_path):
    index_dir = tmp_path / "index"
    build_faiss_index(docs=load_knowledge_base(roots=(WIKI_DIR,)), index_dir=index_dir, embeddings=HashingEmbeddings(dim=256))
    with pytest.raises(ValueError, match="built 256 wide and this embedder returns 64"):
        load_faiss_index(index_dir, embeddings=HashingEmbeddings(dim=64))
