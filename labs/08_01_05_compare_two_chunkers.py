# %%
"""Lab 22.5: compare two chunkers on one DataFlow policy question.

What we build: we cut the DataFlow support procedures file two ways, by character count at three sizes and
by heading, count the orphans each cut leaves, and you type the heading cut yourself. Then both cuts answer
one question in a small in-memory FAISS index (Section 23 builds the real one): how fast must a P0 ticket
get a first response for an Enterprise customer.

What you learn: 22.4's idea made real. A chunk size is a measurement, an orphan is a fact cut away from its
name, and a cut that writes the heading path into each piece keeps the name with the fact. And nearest is not
right: FAISS here returns an L2 distance, lower is nearer, and the wrong passage can sit nearer the question.

What will be true on your screen: recursive_size 300 chunks 89 orphans 17, then 49 and 4 at 512, 21 and 1
at 1000, heading_sections 37 with heading_orphans 0 and the refund path, the embedder read off the object,
each cut's top passage with its distance, has_p0 and has_one_hour, and the measured lines that say which cut
kept the fact. Then python -m pytest tests/test_lab_08_01_05.py -q passes.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

import config
from dataflow.rag.chunk import HEADER_SPLIT, chunk_recursive, heading_path, orphan_count
from dataflow.rag.load import KB_DIR, load_knowledge_base

path = KB_DIR / "internal_operations" / "support_operations" / "customer_support_procedures.markdown"
docs = load_knowledge_base(roots=(path,))
print("file", docs[0].metadata["source"])
print("characters", len(docs[0].page_content))


# %%
# The character cut at three sizes, no overlap. orphan_count is the ruler: a chunk that starts
# mid-list or mid-table with no heading anywhere in it.
for size in (300, 512, 1000):
    pieces = chunk_recursive(docs, size, 0)
    print("recursive_size", size, "chunks", len(pieces), "orphans", orphan_count(pieces))
recursive_300 = chunk_recursive(docs, 300, 0)
first_orphan = next(piece for piece in recursive_300 if orphan_count([piece]))
print("first_orphan_at_300", first_orphan.page_content.splitlines()[0])


# %%
# TYPE THIS: chunk_by_heading. The signature and docstring are given; you type the body.
# Its finished copy is dataflow/rag/chunk.py, which builds every index in Sections 23 to 25.
def chunk_by_heading(docs: list[Document]) -> list[Document]:
    """Heading cut for markdown. Recursive fallback for the rest. Prepends the heading path as the first line of each chunk so the embedder sees the section name with the fact."""
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADER_SPLIT, strip_headers=True)
    out: list[Document] = []
    for doc in docs:
        source = str(doc.metadata.get("source") or "").lower()
        if not source.endswith((".md", ".markdown")):
            out.extend(chunk_recursive([doc], chunk_size=1000, chunk_overlap=0))
            continue
        for piece in splitter.split_text(doc.page_content):
            meta = {**doc.metadata, **piece.metadata}
            path_line = heading_path(meta)
            if path_line:
                meta["heading_path"] = path_line
            text = piece.page_content
            if path_line and not text.startswith(path_line):
                text = path_line + "\n" + text
            out.append(Document(page_content=text, metadata=meta))
    return out


# BREAK: delete the two lines that write the path into the text,
#     if path_line and not text.startswith(path_line):
#         text = path_line + "\n" + text
# run the lab, then python -m pytest tests/test_lab_08_01_05.py -q and read the red line.
# git checkout -- labs/08_01_05_compare_two_chunkers.py puts them back.

heading = chunk_by_heading(docs)
heading_orphans = orphan_count(heading)
print("heading_sections", len(heading))
print("heading_orphans", heading_orphans)
refund = next(chunk for chunk in heading if chunk.metadata.get("h3") == "6.1 Authorization Levels")
print("refund_first_line", refund.page_content.splitlines()[0])


# %%
# One question, two in-memory indexes, the same embedder for both.
question = "How fast must a P0 ticket get a first response for an Enterprise customer?"
embeddings = config.get_embeddings()
print("question", question)
print("embedder", type(embeddings).__name__, getattr(embeddings, "model", None) or getattr(embeddings, "model_name", None))


def top(chunks: list[Document], name: str) -> tuple[float, bool, bool]:
    doc, distance = FAISS.from_documents(chunks, embeddings).similarity_search_with_score(question, k=1)[0]
    has_p0, has_one_hour = "P0" in doc.page_content, "1 hour" in doc.page_content
    print(name, "distance", round(float(distance), 4), "has_p0", has_p0, "has_one_hour", has_one_hour)
    print(doc.page_content[:400])
    return float(distance), has_p0, has_one_hour


heading_distance, heading_p0, heading_hour = top(heading, "heading_cut")
recursive_distance, recursive_p0, recursive_hour = top(recursive_300, "recursive_300")


# %%
# What the run measured, not what we hoped.
print("heading_cut_kept_p0_with_one_hour", heading_p0 and heading_hour)
print("recursive_300_kept_p0_with_one_hour", recursive_p0 and recursive_hour)
print("nearer_passage", "heading_cut" if heading_distance < recursive_distance else "recursive_300")
