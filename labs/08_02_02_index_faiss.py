# %% [markdown]
# Index the DataFlow corpus in FAISS.
#
# When this works, the index is built over customer facing pages plus
# business data, the embedder name and dimension print, and a billing
# question retrieves the extra-user row with its source path. Then
# embed the query with a different model and print what happens.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_ollama import OllamaEmbeddings

from config import EMBED_MODEL, NO_TOOLS_MODEL, _ollama_base, get_embeddings
from dataflow.rag.chunk import chunk_by_heading
from dataflow.rag.faiss_index import (
    INDEX_DIR,
    build_faiss_index,
    measured_dimension,
    search,
)
from dataflow.rag.load import KB_DIR, WIKI_DIR, load_knowledge_base

docs = load_knowledge_base(
    roots=(KB_DIR / "customer_facing", KB_DIR / "business_data", WIKI_DIR)
)
chunks = chunk_by_heading(docs)
print("chunk_count", len(chunks))
print("embedder", EMBED_MODEL)
index = build_faiss_index(docs=docs, chunker="heading", index_dir=INDEX_DIR)
width = measured_dimension()
print("dimension", width)

# %%
question = "How much does an extra user cost on the Professional plan?"
print("question", question)
hits = search(index, question, k=3)
top = hits[0]
print("top_source", top.get("source"))
print("top_row", top.get("row"))
print("top_folder", top.get("folder"))
print("top_score", top.get("score"))
print("top_passage")
print(top.get("text", "")[:500])

# %%
print("break_wrong_embedder", NO_TOOLS_MODEL)
try:
    other = OllamaEmbeddings(model=NO_TOOLS_MODEL, base_url=_ollama_base())
    query_vec = other.embed_query(question)
    print("wrong_embedder_dimension", len(query_vec))
    print("index_dimension", width)
    wrong_hits = index.similarity_search_by_vector(query_vec, k=3)
    print("wrong_embedder_top")
    for doc in wrong_hits:
        print("source", (doc.metadata or {}).get("source"))
        print("text", doc.page_content[:240])
        print("---")
except Exception as err:
    print("wrong_embedder_error", type(err).__name__ + ":", err)

# %%
print("restore_embedder", EMBED_MODEL)
restored = get_embeddings()
print("restore_dimension", len(restored.embed_query("dimension probe")))
again = search(index, question, k=1)
print("restore_source", again[0].get("source"))
print("restore_row", again[0].get("row"))
