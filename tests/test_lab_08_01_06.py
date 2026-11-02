"""Lab 08.01.06 (22.6), load_docx typed by the student. No model. Skips with a reason where a reader is not installed."""

import runpy
from pathlib import Path

import pytest

pytest.importorskip("pypdf", reason="pypdf is in requirements.txt; this venv has not installed it")
pytest.importorskip("docx", reason="python-docx is in requirements.txt; this venv has not installed it")

from dataflow.rag.load import DOCUMENTS_DIR, load_docx  # noqa: E402
from tests.fixtures.lab_copy import lab_copy  # noqa: E402

LAB = Path(__file__).resolve().parents[1] / "labs" / "08_01_06_load_pdf_and_word.py"


def _out(path, capsys):
    namespace = runpy.run_path(str(path), run_name="__main__")
    return namespace, capsys.readouterr().out.splitlines()


def test_three_loads_keep_the_headings(capsys):
    _, out = _out(LAB, capsys)
    for line in (
        "pdf_library_has_h2 False",
        "pdf_headings_match_markdown True",
        "word_headings_match_markdown True",
        "words_kept True",
        "default_load_files 21 office_files_in_it 0",
    ):
        assert line in out, line


def test_typed_loader_matches_the_module(capsys):
    lab, _ = _out(LAB, capsys)
    path = DOCUMENTS_DIR / "product_user_guide.docx"
    mine, theirs = lab["load_docx"](path), load_docx(path)
    assert [(d.page_content, d.metadata) for d in mine] == [(d.page_content, d.metadata) for d in theirs]


def test_the_break_loses_the_word_headings(tmp_path, capsys):
    line = '        level = int(style.split()[-1]) if style.startswith("Heading ") and style.split()[-1].isdigit() else 0\n'
    broken = lab_copy(LAB, tmp_path, line, "        level = 0\n")
    _, out = _out(broken, capsys)
    assert "word_headings_match_markdown False" in out
