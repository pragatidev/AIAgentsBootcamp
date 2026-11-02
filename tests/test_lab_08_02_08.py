"""Lab 08.02.08 (23.8), diff typed by the student. A hashing embedder stands in for the real one here, and only here."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.rag import faiss_index as FI
from dataflow.rag.manifest import diff as module_diff
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "08_02_08_reindex_a_changed_file.py"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    emb = HashingEmbeddings()
    monkeypatch.setattr(config, "get_embeddings", lambda: emb)
    monkeypatch.setattr(FI, "get_embeddings", lambda: emb)


def _out(path, capsys):
    namespace = runpy.run_path(str(path), run_name="__main__")
    return namespace, capsys.readouterr().out.splitlines()


def test_refresh_embeds_only_the_changed_file(capsys):
    _, out = _out(LAB, capsys)
    nothing = next(line for line in out if line.startswith("refresh_nothing_changed"))
    assert "changed [] removed [] embedded 0" in nothing
    after = next(line for line in out if line.startswith("refresh_after_edit"))
    assert "changed ['shipping.md']" in after and "embedded 0" not in after
    assert "new_sentence_found True" in out and "copies_of_new_sentence 1" in out


@pytest.mark.parametrize(
    "files",
    [{"a.md": "1", "b.md": "2"}, {"a.md": "1", "b.md": "9", "d.md": "4"}, {}],
)
def test_typed_diff_matches_the_module(capsys, files):
    lab, _ = _out(LAB, capsys)
    meta = {"files": {"a.md": {"sha256": "1"}, "b.md": {"sha256": "2"}, "c.md": {"sha256": "3"}}}
    assert lab["diff"](meta, files) == module_diff(meta, files)


def test_the_break_serves_the_old_page(tmp_path, capsys):
    line = '        "changed": sorted(source for source in files if source in indexed and files[source] != indexed[source]),\n'
    _, out = _out(lab_copy(LAB, tmp_path, line, '        "changed": [],\n'), capsys)
    after = next(line for line in out if line.startswith("refresh_after_edit"))
    assert "changed [] removed [] embedded 0" in after
    assert "new_sentence_found False" in out and "copies_of_new_sentence 0" in out
