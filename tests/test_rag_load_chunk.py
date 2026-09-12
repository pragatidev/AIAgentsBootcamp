"""8.1 loaders and chunkers. No live model."""

from pathlib import Path

from langchain_community.document_loaders import TextLoader

from dataflow.rag.chunk import chunk_by_heading, chunk_recursive, orphan_count
from dataflow.rag.load import (
    KB_DIR,
    list_knowledge_files,
    load_json,
    load_knowledge_base,
)

ROOT = Path(__file__).resolve().parents[1]
PROCEDURES = (
    KB_DIR
    / "internal_operations"
    / "support_operations"
    / "customer_support_procedures.markdown"
)


def test_twenty_files_loaded():
    files = list_knowledge_files()
    assert len(files) == 20
    docs = load_knowledge_base()
    assert len(docs) > 20
    sources = {doc.metadata["source"] for doc in docs}
    assert "dataflow/wiki/return_policy.md" in sources
    folders = {doc.metadata["folder"] for doc in docs}
    assert "wiki" in folders
    assert "business_data" in folders
    assert "customer_facing" in folders


def test_csv_rows_keep_row_metadata():
    docs = [
        doc
        for doc in load_knowledge_base()
        if str(doc.metadata.get("source", "")).endswith("billing_and_pricing.csv")
    ]
    assert len(docs) == 63
    assert "row" in docs[0].metadata
    assert docs[0].metadata["folder"] == "business_data"
    assert "Number of users" in docs[0].page_content
    assert "\\" not in docs[0].metadata["source"]


def test_json_loader_by_hand(tmp_path):
    sample = tmp_path / "rows.json"
    sample.write_text('[{"name": "a"}, {"name": "b"}]\n', encoding="utf-8")
    docs = load_json(sample)
    assert len(docs) == 2
    assert docs[0].metadata["record"] == 0
    assert docs[1].metadata["record"] == 1
    assert '"name": "a"' in docs[0].page_content
    notes = load_json(
        KB_DIR / "internal_operations" / "product_releases" / "release_notes.json"
    )
    assert len(notes) >= 2
    assert "source" in notes[0].metadata
    assert "record" in notes[0].metadata
    assert notes[0].metadata["source"].endswith("release_notes.json")


def test_recursive_orphans_at_300():
    loaded = TextLoader(str(PROCEDURES), encoding="utf-8").load()
    chunks = chunk_recursive(loaded, chunk_size=300, chunk_overlap=0)
    assert len(chunks) == 89
    assert orphan_count(chunks) == 17
    first_orphan = next(
        chunk.page_content.splitlines()[0]
        for chunk in chunks
        if orphan_count([chunk])
    )
    assert first_orphan.startswith(
        "- Response Time: 1 hour (billing_and_pricing.csv, Enterprise SLA)."
    )


def test_heading_split_keeps_section():
    loaded = TextLoader(str(PROCEDURES), encoding="utf-8").load()
    loaded[0].metadata["source"] = (
        "dataflow/knowledge_base/internal_operations/"
        "support_operations/customer_support_procedures.markdown"
    )
    chunks = chunk_by_heading(loaded)
    assert len(chunks) == 37
    refund = [
        chunk
        for chunk in chunks
        if chunk.metadata.get("h3") == "6.1 Authorization Levels"
    ]
    assert refund
    first = refund[0].page_content.splitlines()[0]
    assert first.startswith("6. Refund and Cancellation Procedures")
    assert "6.1 Authorization Levels" in first
    assert refund[0].metadata.get("h2") == "6. Refund and Cancellation Procedures"
