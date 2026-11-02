# %%
"""Lab 22.3: load the DataFlow knowledge base.

What we build: you type the two small functions that load one file, one that picks the loader by the file's
type (a text page whole, a csv one document per row, a json file one per record) and one that stamps every
document with where it came from, then you load every file under the knowledge base and the wiki with them.
No model and no key in this lab; it runs with Ollama off.

What you learn: the loader decides the unit of meaning, and the source survives loading. Section 23's
retrieve scope reads the folder on every document, and Section 25's citations read the path and the row.

What will be true on your screen: file_count 21 and document_count 272, the files by suffix and the
documents by folder, the first billing csv row with its source, row 0 and folder, jq_installed False and
the library json loader's ImportError, load_json_documents 12, and same_as_module True. Then
python -m pytest tests/test_lab_08_01_03.py -q passes.
"""

from collections import Counter
from importlib.util import find_spec
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_community.document_loaders import CSVLoader, TextLoader
from langchain_core.documents import Document

from dataflow.rag.load import (
    CSV_SUFFIXES,
    JSON_SUFFIXES,
    KB_DIR,
    TEXT_SUFFIXES,
    folder_for,
    list_knowledge_files,
    load_json,
    load_knowledge_base,
    relative_source,
)


# %%
# TYPE THIS: stamp and load_one. The signatures and docstrings are given; you type the bodies.
# Their finished copies are _stamp and _load_one in dataflow/rag/load.py, which every later lab uses.
def stamp(doc: Document, path: Path, extra: dict | None = None) -> Document:
    """Put the repo-relative source and the folder on this document, plus any extra keys, and return it."""
    metadata = dict(doc.metadata or {})
    metadata["source"] = relative_source(path)
    metadata["folder"] = folder_for(path)
    if extra:
        metadata.update(extra)
    doc.metadata = metadata
    return doc


def load_one(path: Path) -> list[Document]:
    """Pick the loader by suffix: text files whole, a csv one document per row, a json file one per record (load_json). Stamp every document. Unknown suffix: []."""
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return [stamp(doc, path) for doc in TextLoader(str(path), encoding="utf-8").load()]
    if suffix in CSV_SUFFIXES:
        return [stamp(doc, path) for doc in CSVLoader(str(path), encoding="utf-8").load()]
    if suffix in JSON_SUFFIXES:
        return load_json(path)
    return []


# BREAK: send a csv to the text loader. Change the first test in load_one to
#     if suffix in TEXT_SUFFIXES | CSV_SUFFIXES:
# run the lab, then python -m pytest tests/test_lab_08_01_03.py -q and read the red line.
# git checkout -- labs/08_01_03_load_knowledge_base.py puts it back; git status --short then prints nothing.


# %%
# Every file under the knowledge base and the wiki, through your two functions.
files = list_knowledge_files()
docs = [doc for path in files for doc in load_one(path)]
print("file_count", len(files))
print("document_count", len(docs))
print("files_by_suffix", dict(sorted(Counter(path.suffix.lower() for path in files).items())))
print("documents_by_folder", dict(sorted(Counter(doc.metadata["folder"] for doc in docs).items())))

billing = [doc for doc in docs if doc.metadata["source"].endswith("billing_and_pricing.csv")]
print("billing_csv_documents", len(billing))
print("billing_first_document_metadata", billing[0].metadata)
print("billing_first_document_characters", len(billing[0].page_content))
print(billing[0].page_content[:200])


# %%
# The library's json loader needs the jq package, which this course does not install.
json_path = KB_DIR / "internal_operations" / "product_releases" / "release_notes.json"
print("jq_installed", find_spec("jq") is not None)
try:
    from langchain_community.document_loaders import JSONLoader

    JSONLoader(file_path=str(json_path), jq_schema=".releases[]").load()
    print("JSONLoader_loaded (jq is installed on this machine)")
except ImportError as err:
    print("JSONLoader_error", type(err).__name__ + ":", err)

hand = load_json(json_path)
print("load_json_documents", len(hand))
print("load_json_first_metadata", hand[0].metadata)


# %%
# Your copy against the finished one: the same sources, folders, rows, records and text, in the same order.
def fingerprint(doc: Document) -> tuple:
    meta = doc.metadata
    return (meta["source"], meta["folder"], meta.get("row"), meta.get("record"), doc.page_content)


print("same_as_module", [fingerprint(doc) for doc in docs] == [fingerprint(doc) for doc in load_knowledge_base()])
