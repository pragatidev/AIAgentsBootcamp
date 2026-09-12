# %% [markdown]
# Compare two chunkers on one DataFlow policy question.
#
# When this works, the character cut prints chunk and orphan counts
# at 300, 512, and 1000, the heading cut prints 37 sections and the
# refund rule's heading path, both cuts are embedded in FAISS, and
# the P0 Enterprise first-response question prints the top passage
# from each cut plus whether the P0 name survived. The winner is
# the cut that kept the name with the fact.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS

from config import EMBED_MODEL, get_embeddings
from dataflow.rag.chunk import chunk_by_heading, chunk_recursive, orphan_count
from dataflow.rag.load import KB_DIR

path = (
    KB_DIR
    / "internal_operations"
    / "support_operations"
    / "customer_support_procedures.markdown"
)
docs = TextLoader(str(path), encoding="utf-8").load()
docs[0].metadata["source"] = (
    "dataflow/knowledge_base/internal_operations/"
    "support_operations/customer_support_procedures.markdown"
)
print("file", docs[0].metadata["source"])
print("characters", len(docs[0].page_content))

EXPECTED = {300: (89, 17), 512: (49, 4), 1000: (21, 1)}
recursive_cuts: dict[int, list] = {}
for size in (300, 512, 1000):
    chunks = chunk_recursive(docs, chunk_size=size, chunk_overlap=0)
    orphans = orphan_count(chunks)
    recursive_cuts[size] = chunks
    expected_chunks, expected_orphans = EXPECTED[size]
    print(
        "recursive_size",
        size,
        "chunks",
        len(chunks),
        "orphans",
        orphans,
        "expected",
        f"{expected_chunks}/{expected_orphans}",
    )
    if (len(chunks), orphans) != (expected_chunks, expected_orphans):
        print(
            "recursive_diff",
            "measured",
            f"{len(chunks)}/{orphans}",
            "fable",
            f"{expected_chunks}/{expected_orphans}",
        )
    if size == 300:
        first_orphan = None
        for chunk in chunks:
            if orphan_count([chunk]):
                first_orphan = chunk.page_content.splitlines()[0]
                break
        print("first_orphan_at_300", first_orphan)

# %%
heading = chunk_by_heading(docs)
print("heading_sections", len(heading))
refund = [
    chunk
    for chunk in heading
    if chunk.metadata.get("h3") == "6.1 Authorization Levels"
    or "6.1 Authorization Levels" in chunk.page_content.splitlines()[0]
]
print("refund_chunks", len(refund))
if refund:
    print("refund_heading_path", refund[0].page_content.splitlines()[0])
    print("refund_h2", refund[0].metadata.get("h2"))
    print("refund_h3", refund[0].metadata.get("h3"))

# %%
question = (
    "How fast must a P0 ticket get a first response for an Enterprise customer?"
)
print("question", question)
print("embedder", EMBED_MODEL)
embeddings = get_embeddings()

small = recursive_cuts[300]
heading_store = FAISS.from_documents(heading, embeddings)
small_store = FAISS.from_documents(small, embeddings)

heading_hit = heading_store.similarity_search_with_score(question, k=1)[0]
small_hit = small_store.similarity_search_with_score(question, k=1)[0]


def show(label: str, pair) -> bool:
    doc, score = pair
    text = doc.page_content
    has_p0 = "P0" in text
    print(label, "score", score)
    print(label, "has_p0", has_p0)
    print(label, "passage")
    print(text[:500])
    return has_p0


heading_has = show("heading", heading_hit)
small_has = show("recursive_300", small_hit)
if heading_has and not small_has:
    winner = "heading cut: P0 survived with the one hour fact; 300 char cut dropped the name"
elif heading_has and small_has:
    winner = "both cuts kept P0 on this question; heading still has zero orphans"
elif small_has and not heading_has:
    winner = "recursive 300 kept P0 and heading did not (measured, unexpected)"
else:
    winner = "neither top passage named P0 (measured)"
print("winner", winner)
