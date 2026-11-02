"""Lab 08.01.03 (22.3), stamp and load_one typed by the student. No model, no embedder, no network."""

import runpy
from pathlib import Path

import pytest

from dataflow.rag import load as M
from tests.fixtures.lab_copy import lab_copy

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "08_01_03_load_knowledge_base.py"
PATHS = [
    M.KB_DIR / "business_data" / "billing_and_pricing.csv",
    M.KB_DIR / "internal_operations" / "product_releases" / "release_notes.json",
    M.WIKI_DIR / "security.md",
    M.KB_DIR / "customer_facing" / "product_user_guide.markdown",
]


def _lines(capsys):
    return capsys.readouterr().out.splitlines()


@pytest.fixture(scope="module")
def lab():
    return runpy.run_path(str(LAB), run_name="__main__")


def test_the_run_prints_the_counts(capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = _lines(capsys)
    for line in ("file_count 21", "document_count 272", "billing_csv_documents 63", "load_json_documents 12", "same_as_module True"):
        assert line in out
    assert "billing_first_document_metadata {'source': 'dataflow/knowledge_base/business_data/billing_and_pricing.csv', 'row': 0, 'folder': 'business_data'}" in out


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.name)
def test_load_one_matches_the_module(lab, path):
    mine, theirs = lab["load_one"](path), M._load_one(path)
    assert [(d.page_content, d.metadata) for d in mine] == [(d.page_content, d.metadata) for d in theirs]


def test_stamp_matches_the_module(lab):
    from langchain_core.documents import Document

    path = M.WIKI_DIR / "return_policy.md"
    mine = lab["stamp"](Document(page_content="x", metadata={"a": 1}), path, extra={"row": 3})
    theirs = M._stamp(Document(page_content="x", metadata={"a": 1}), path, extra={"row": 3})
    assert mine.metadata == theirs.metadata


def test_the_break_turns_a_price_list_into_one_blob(tmp_path, capsys):
    broken = lab_copy(LAB, tmp_path, "    if suffix in TEXT_SUFFIXES:\n", "    if suffix in TEXT_SUFFIXES | CSV_SUFFIXES:\n")
    runpy.run_path(str(broken), run_name="__main__")
    out = _lines(capsys)
    assert "billing_csv_documents 1" in out
    assert "document_count 78" in out
    assert "same_as_module False" in out
