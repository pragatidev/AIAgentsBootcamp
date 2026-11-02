# %%
"""Lab 23.8: re-index one changed DataFlow file.

What we build: an index that follows its files. You type the small function that compares what an index
was built from with the files on disk now: which were added, which changed, which were removed. The lab
copies the DataFlow wiki to a temporary folder (the repo's wiki is never edited), builds an index there,
refreshes it with nothing changed, edits one line of the copy's shipping page, and refreshes again.

What you learn: an index is a copy, and a copy goes stale. Every saved index here carries index_meta.json:
the embedder that built it and, per file, a hash of its bytes and the ids of its chunks. A changed file is
found by its hash (never its timestamp, which git changes without changing a word), its old chunks are
deleted by id, and only that file is embedded again. The desk's own indexes refresh the same way.

What will be true on your screen: the embedder off the object, the first build's files and chunks, a
refresh with nothing changed that prints changed [] and embedded 0, the edit, a refresh that names the
shipping page and embeds only its chunks, and a search that finds the new sentence once with its source.
Then python -m pytest tests/test_lab_08_02_08.py -q passes.
"""

from pathlib import Path
import shutil
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.rag.faiss_index import build_faiss_index, refresh_index, search
from dataflow.rag.load import WIKI_DIR, load_knowledge_base
from dataflow.rag.manifest import load_manifest


# %%
# TYPE THIS: diff. The signature and docstring are given; you type the body.
# Its finished copy is diff in dataflow/rag/manifest.py, which the desk's indexes refresh with.
def diff(meta: dict, files: dict) -> dict:
    """Compare the manifest's files with the files on disk now (source to sha256). added: on disk, not in the manifest. removed: in the manifest, not on disk. changed: in both, with a different hash. Each list is sorted."""
    indexed = {source: row["sha256"] for source, row in (meta.get("files") or {}).items()}
    return {
        "added": sorted(source for source in files if source not in indexed),
        "changed": sorted(source for source in files if source in indexed and files[source] != indexed[source]),
        "removed": sorted(source for source in indexed if source not in files),
    }


# BREAK: forget the changed files. Change the changed line to
#         "changed": [],
# run the lab and read the second refresh and new_sentence_found, then python -m pytest tests/test_lab_08_02_08.py -q.
# git checkout -- labs/08_02_08_reindex_a_changed_file.py puts it back.


# %%
work = Path(tempfile.mkdtemp(prefix="reindex-"))
wiki = work / "wiki"
shutil.copytree(WIKI_DIR, wiki)
index_dir = work / "index"
embeddings = config.get_embeddings()
print("embedder", type(embeddings).__name__, getattr(embeddings, "model", None) or getattr(embeddings, "model_name", None))
index = build_faiss_index(docs=load_knowledge_base(roots=(wiki,)), index_dir=index_dir, embeddings=embeddings)
meta = load_manifest(index_dir)
print("built files", [Path(source).name for source in meta["files"]], "chunks", meta["count"])


def refresh(label: str) -> dict:
    result = refresh_index(index, index_dir, (wiki,), diff_fn=diff)
    print(label, "added", [Path(s).name for s in result["added"]], "changed", [Path(s).name for s in result["changed"]],
          "removed", [Path(s).name for s in result["removed"]], "embedded", result["embedded"], "chunks", result["count"])
    return result


refresh("refresh_nothing_changed")


# %%
# One edit to the copy's shipping page: this lab's own sentence, in its own temporary folder.
NEW_SENTENCE = "Lab 23.8 edit: express shipping arrives in two business days inside the country."
page = wiki / "shipping.md"
page.write_text(page.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + NEW_SENTENCE + "\n", encoding="utf-8")
print("edited", page.name)
refresh("refresh_after_edit")

hits = search(index, NEW_SENTENCE, k=3)
print("top_hit", Path(hits[0]["source"]).name, round(hits[0]["score"], 4))
print("new_sentence_found", NEW_SENTENCE in hits[0]["text"])
print("copies_of_new_sentence", sum(NEW_SENTENCE in doc.page_content for doc in index.docstore._dict.values()))
shutil.rmtree(work, ignore_errors=True)
