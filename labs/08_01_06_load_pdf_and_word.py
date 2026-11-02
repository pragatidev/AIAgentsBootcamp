# %%
"""Lab 22.6: load a PDF and a Word file without losing their headings.

What we build: the DataFlow user guide exists three ways, the markdown page in the knowledge base and a PDF
and a Word file rendered from it under dataflow/documents/ (no fact added). You type the Word loader, then
load all three side by side: the markdown by heading, the PDF twice (the library's PyPDFLoader, and our
load_pdf, which reads the PDF's bookmarks), and the Word file with your loader. No model and no key.

What you learn: 22.2's idea on the file types a company has. A loader decides what a document is: the
library PDF loader gives you pages, so a heading is just a line on a page and a citation can name only the
page; a Word file keeps its headings as styles, and a PDF keeps them as bookmarks, so a loader that reads
them gives each section its heading path, the shape every citation in Section 25 prints.

What will be true on your screen: the document count and first metadata of each load, the library PDF
loader's pages with no h2, and three checks: pdf_headings_match_markdown True, word_headings_match_markdown
True and words_kept True. The office files load only when asked (suffixes=); the default load still gives 21
files. Then python -m pytest tests/test_lab_08_01_06.py -q passes.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from dataflow.rag.chunk import chunk_by_heading, heading_path
from dataflow.rag.load import DOCUMENTS_DIR, KB_DIR, OFFICE_SUFFIXES, _stamp, list_knowledge_files, load_knowledge_base

markdown = KB_DIR / "customer_facing" / "product_user_guide.markdown"
pdf = DOCUMENTS_DIR / "product_user_guide.pdf"
word = DOCUMENTS_DIR / "product_user_guide.docx"


# %%
# TYPE THIS: load_docx. The signature and docstring are given; you type the body.
# Its finished copy is load_docx in dataflow/rag/load.py.
def load_docx(path: Path) -> list[Document]:
    """A Word file as one document per section: a paragraph in a Heading 1 to 3 style starts a new section. Each document carries h1 to h3 and heading_path from the headings above it, and is stamped with its source and folder."""
    from docx import Document as WordFile

    docs, heads, lines = [], {}, []
    for para in WordFile(str(path)).paragraphs:
        style = para.style.name if para.style is not None else ""
        level = int(style.split()[-1]) if style.startswith("Heading ") and style.split()[-1].isdigit() else 0
        if 1 <= level <= 3:
            if lines:
                docs.append(_stamp(Document(page_content="\n".join(lines), metadata={**heads, "heading_path": heading_path(heads)}), path))
            heads = {key: value for key, value in heads.items() if int(key[1]) < level}
            heads[f"h{level}"] = para.text.strip()
            lines = []
        elif para.text.strip():
            lines.append(para.text.strip())
    if lines:
        docs.append(_stamp(Document(page_content="\n".join(lines), metadata={**heads, "heading_path": heading_path(heads)}), path))
    return docs


# BREAK: ignore the styles, so every paragraph is body text. Change the level line to
#         level = 0
# run the lab and read word_headings_match_markdown, then python -m pytest tests/test_lab_08_01_06.py -q.
# git checkout -- labs/08_01_06_load_pdf_and_word.py puts it back.


# %%
def show(name: str, docs: list[Document]) -> None:
    print(name, "documents", len(docs))
    print(name, "first_metadata", {key: value for key, value in docs[0].metadata.items() if key in ("source", "folder", "page", "h2", "h3", "heading_path")})


md_sections = chunk_by_heading(load_knowledge_base(roots=(markdown,)))
show("markdown", md_sections)
pages = PyPDFLoader(str(pdf)).load()
show("pdf_library_pages", pages)
print("pdf_library_has_h2", any("h2" in page.metadata for page in pages))
pdf_sections = load_knowledge_base(roots=(pdf,), suffixes=OFFICE_SUFFIXES)
show("pdf_bookmarks", pdf_sections)
word_sections = load_docx(word)
show("word", word_sections)


# %%
def heads(docs: list[Document]) -> list[str]:
    return sorted({doc.metadata["heading_path"] for doc in docs if doc.metadata.get("h2")})


print("headings_in_markdown", len(heads(md_sections)))
print("pdf_headings_match_markdown", heads(pdf_sections) == heads(md_sections))
print("word_headings_match_markdown", heads(word_sections) == heads(md_sections))
first_h3 = next((doc for doc in word_sections if doc.metadata.get("h3")), None)
print("word_first_h3_section", first_h3.metadata["heading_path"] if first_h3 else None)
print(first_h3.page_content[:300] if first_h3 else word_sections[0].page_content[:300])
joined = " ".join(" ".join(doc.page_content.split()) for doc in word_sections)
print("words_kept", all(" ".join(doc.page_content.split()[:6]) in joined for doc in pdf_sections))
print("default_load_files", len(list_knowledge_files()), "office_files_in_it", sum(p.suffix in OFFICE_SUFFIXES for p in list_knowledge_files()))
