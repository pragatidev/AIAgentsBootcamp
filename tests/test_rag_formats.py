"""PDF and Word loaders (22.6). The known answer is the markdown page the two files were rendered from. No model."""

import importlib.util
import re

import pytest

from dataflow.rag.load import (
    DOCUMENTS_DIR,
    KB_DIR,
    OFFICE_SUFFIXES,
    list_knowledge_files,
    load_knowledge_base,
)

SOURCE = KB_DIR / "customer_facing" / "product_user_guide.markdown"
PDF = DOCUMENTS_DIR / "product_user_guide.pdf"
DOCX = DOCUMENTS_DIR / "product_user_guide.docx"

_spec = importlib.util.spec_from_file_location("make_format_samples", DOCUMENTS_DIR.parents[1] / "scripts" / "make_format_samples.py")
samples = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(samples)


def _blocks():
    return samples.blocks(SOURCE.read_text(encoding="utf-8"))


def _headings(level):
    return [text for kind, lvl, text in _blocks() if kind == "heading" and lvl == level]


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _missing_lines(docs):
    joined = _norm(" ".join(doc.page_content for doc in docs))
    return [text for kind, _, text in _blocks() if kind == "line" and _norm(text) not in joined]


def test_default_load_skips_office_files():
    assert not any(p.suffix in OFFICE_SUFFIXES for p in list_knowledge_files())
    assert sorted(p.name for p in list_knowledge_files((DOCUMENTS_DIR,), suffixes=OFFICE_SUFFIXES)) == [
        "product_user_guide.docx",
        "product_user_guide.pdf",
    ]


def test_pdf_keeps_its_headings_and_pages():
    pytest.importorskip("pypdf", reason="pypdf is in requirements.txt; this venv has not installed it")
    docs = load_knowledge_base(roots=(PDF,), suffixes=OFFICE_SUFFIXES)
    assert {d.metadata["source"] for d in docs} == {"dataflow/documents/product_user_guide.pdf"}
    assert {d.metadata["folder"] for d in docs} == {"documents"}
    assert sorted({d.metadata["h2"] for d in docs if d.metadata.get("h2")}) == sorted(_headings(2))
    assert sorted({d.metadata["h3"] for d in docs if d.metadata.get("h3")}) == sorted(_headings(3))
    assert all(isinstance(d.metadata["page"], int) and d.metadata["page"] >= 1 for d in docs)


def test_pdf_words_match_markdown():
    pytest.importorskip("pypdf", reason="pypdf is in requirements.txt; this venv has not installed it")
    assert _missing_lines(load_knowledge_base(roots=(PDF,), suffixes=OFFICE_SUFFIXES)) == []


def test_docx_keeps_headings():
    pytest.importorskip("docx", reason="python-docx is in requirements.txt; this venv has not installed it")
    docs = load_knowledge_base(roots=(DOCX,), suffixes=OFFICE_SUFFIXES)
    h2 = list(dict.fromkeys(d.metadata["h2"] for d in docs if d.metadata.get("h2")))
    h3 = list(dict.fromkeys(d.metadata["h3"] for d in docs if d.metadata.get("h3")))
    assert h2 == _headings(2) and h3 == _headings(3)
    refund = next(d for d in docs if d.metadata.get("h3") == _headings(3)[0])
    assert refund.metadata["heading_path"] == f"{refund.metadata['h2']} > {refund.metadata['h3']}"
    assert _missing_lines(docs) == []


def test_library_pdf_loader_keeps_pages_not_headings():
    pytest.importorskip("pypdf", reason="pypdf is in requirements.txt; this venv has not installed it")
    from langchain_community.document_loaders import PyPDFLoader

    pages = PyPDFLoader(str(PDF)).load()
    assert len(pages) >= 2 and all("page" in p.metadata for p in pages)
    assert not any("h2" in p.metadata for p in pages)
