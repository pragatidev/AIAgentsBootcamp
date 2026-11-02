"""Lab 08.01.05 (22.5), chunk_by_heading typed by the student. A hashing embedder stands in for the real one here, and only here."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.rag import chunk as M
from dataflow.rag.load import KB_DIR, load_knowledge_base
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "08_01_05_compare_two_chunkers.py"
PROCEDURES = KB_DIR / "internal_operations" / "support_operations" / "customer_support_procedures.markdown"
GUIDE = KB_DIR / "customer_facing" / "troubleshooting_guide.txt"


@pytest.fixture(autouse=True)
def hashing(monkeypatch):
    monkeypatch.setattr(config, "get_embeddings", lambda: HashingEmbeddings())


def _run(path, capsys):
    runpy.run_path(str(path), run_name="__main__")
    return capsys.readouterr().out.splitlines()


def test_the_run_prints_the_measured_counts(capsys):
    out = _run(LAB, capsys)
    for line in (
        "recursive_size 300 chunks 89 orphans 17",
        "recursive_size 512 chunks 49 orphans 4",
        "recursive_size 1000 chunks 21 orphans 1",
        "heading_sections 37",
        "heading_orphans 0",
        "refund_first_line 6. Refund and Cancellation Procedures > 6.1 Authorization Levels",
        "first_orphan_at_300 - Response Time: 1 hour (billing_and_pricing.csv, Enterprise SLA).",
        "embedder HashingEmbeddings None",
    ):
        assert line in out
    assert any(line.startswith("heading_cut distance") for line in out)
    assert any(line.startswith("recursive_300 distance") for line in out)


@pytest.mark.parametrize("path", [PROCEDURES, GUIDE], ids=["markdown", "txt"])
def test_typed_cut_matches_the_module(path):
    lab = runpy.run_path(str(LAB), run_name="lab_08_01_05")
    docs = load_knowledge_base(roots=(path,))
    mine = lab["chunk_by_heading"](docs)
    theirs = M.chunk_by_heading(load_knowledge_base(roots=(path,)))
    span_keys = {"start_index", "line_start", "line_end"}
    assert [c.page_content for c in mine] == [c.page_content for c in theirs]
    assert [{k: v for k, v in c.metadata.items() if k not in span_keys} for c in mine] == [
        {k: v for k, v in c.metadata.items() if k not in span_keys} for c in theirs
    ]


def test_the_break_leaves_orphans(tmp_path, capsys):
    broken = lab_copy(
        LAB,
        tmp_path,
        "            if path_line and not text.startswith(path_line):\n                text = path_line + \"\\n\" + text\n",
        "",
    )
    out = _run(broken, capsys)
    orphans = next(int(line.split()[1]) for line in out if line.startswith("heading_orphans "))
    assert orphans > 0
    assert "refund_first_line 6. Refund and Cancellation Procedures > 6.1 Authorization Levels" not in out
