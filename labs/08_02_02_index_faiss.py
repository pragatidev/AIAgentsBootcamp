# %%
"""Lab 23.2: index the DataFlow corpus in FAISS.

What we build: we turn the customer side of the DataFlow corpus (the customer facing pages, the business
data and the wiki) into a FAISS index on disk. You type the function that chunks, embeds every chunk with
the course embedder and saves it; it writes to its own folder, faiss_index_lab, so a broken build never
becomes the desk's index. Then one billing question, a width check, and the desk's own customer index with
the manifest that says what built it.

What you learn: 23.1's idea made real. An embedding puts meaning in a vector, so a question in words lands
next to a csv row; one embedder must build the index and embed every query, and the width check is how
you know; and the metadata from 22.3 rides inside the index, or the citation is gone.

What will be true on your screen: the embedder read off the object, chunk_count from the index itself,
index_dimension and embedder_dimension with same_width True, the billing question's top hit with its
source, row, folder and distance, and the desk's customer index: its folders, file count and embedder from
index_meta.json. Then python -m pytest tests/test_lab_08_02_02.py -q passes.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

import config
from dataflow.rag.chunk import chunk_by_heading, chunk_recursive
from dataflow.rag.faiss_index import INDEX_DIR, measured_dimension, search
from dataflow.rag.load import KB_DIR, WIKI_DIR, load_knowledge_base, relative_source
from dataflow.rag.manifest import load_manifest

LAB_INDEX_DIR = INDEX_DIR.parent / "faiss_index_lab"


# %%
# TYPE THIS: build_faiss_index. The signature and docstring are given; you type the body.
# Its finished copy is dataflow/rag/faiss_index.py, which also gives every chunk a stable id and writes
# index_meta.json (lab 23.8 uses both).
def build_faiss_index(docs: list[Document], chunker: str = "heading", index_dir: Path | None = None, embeddings=None) -> FAISS:
    """Chunk the documents, embed every chunk with one embedder (config's when none is passed), keep each chunk's metadata, save to index_dir when it is set, and return the index."""
    embeddings = embeddings or config.get_embeddings()
    chunks = chunk_by_heading(docs) if chunker == "heading" else chunk_recursive(docs, chunk_size=1000)
    index = FAISS.from_documents(chunks, embeddings)
    if index_dir is not None:
        Path(index_dir).mkdir(parents=True, exist_ok=True)
        index.save_local(str(index_dir))
    return index


# BREAK: build from the bare text and drop the metadata. Replace the FAISS.from_documents line with
#     index = FAISS.from_texts([chunk.page_content for chunk in chunks], embeddings)
# run the lab, then python -m pytest tests/test_lab_08_02_02.py -q and read the red line.
# git checkout -- labs/08_02_02_index_faiss.py puts it back.


# %%
# The customer side of the corpus, embedded by the embedder config hands out.
roots = (KB_DIR / "customer_facing", KB_DIR / "business_data", WIKI_DIR)
print("folders", [root.name for root in roots])
docs = load_knowledge_base(roots=roots)
embeddings = config.get_embeddings()
print("embedder", type(embeddings).__name__, getattr(embeddings, "model", None) or getattr(embeddings, "model_name", None))
index = build_faiss_index(docs, index_dir=LAB_INDEX_DIR, embeddings=embeddings)
print("chunk_count", index.index.ntotal)
print("index_dimension", index.index.d)
print("embedder_dimension", measured_dimension(embeddings))
print("same_width", index.index.d == measured_dimension(embeddings))
print("saved_to", relative_source(LAB_INDEX_DIR))


# %%
# One billing question. The distance is L2: lower is nearer.
question = "How much does an extra user cost on the Professional plan?"
hit = search(index, question, k=3)[0]
print("question", question)
print("top_source", hit["source"])
print("top_row", hit["row"])
print("top_folder", hit["folder"])
print("top_distance", round(hit["score"], 4))
print(hit["text"][:500])


# %%
# The desk's own customer index: built from the wiki and the customer facing pages only, whatever lab ran
# first, and checked against its manifest every time it is opened.
from dataflow.tools.retrieve import SCOPE_DIRS, get_index

desk = get_index(scope="customer")
meta = load_manifest(SCOPE_DIRS["customer"]) or {}
print("desk_index_folders", meta.get("roots"))
print("desk_index_files", len(meta.get("files") or {}))
print("desk_index_embedder", meta.get("embedder"))
print("desk_index_chunks", desk.index.ntotal)
