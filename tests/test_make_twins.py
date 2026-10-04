"""A rebuilt notebook twin matches the committed one byte for byte, on Windows too."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
TWIN = "labs/00_05_notebook_twin_demo.ipynb"


def git(*args: str, cwd: Path) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True
    )
    return done.stdout


@pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="needs git and a git clone of this repo",
)
def test_rebuilt_twin_shows_no_change_with_autocrlf_false(tmp_path):
    # A checkout with core.autocrlf=false keeps the bytes git stores (LF), so a twin
    # written with CRLF would show every line as changed.
    clone = tmp_path / "clone"
    git("clone", "-q", "-c", "core.autocrlf=false", str(ROOT), str(clone), cwd=tmp_path)
    (clone / TWIN).unlink()
    subprocess.run(
        [sys.executable, "scripts/make_twins.py"], cwd=clone, capture_output=True, check=True
    )
    assert (clone / TWIN).is_file()
    assert git("status", "--porcelain", cwd=clone) == ""


def test_every_twin_is_a_valid_notebook_with_cell_ids():
    # nbformat 4.5 notebooks need an id on every cell; without one nbformat warns that it
    # "will become a hard error in future nbformat versions".
    import warnings

    import nbformat

    twins = sorted((ROOT / "labs").glob("*.ipynb"))
    assert twins
    for twin in twins:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            nb = nbformat.read(twin, as_version=4)
            nbformat.validate(nb)
        ids = [cell["id"] for cell in nb.cells]
        assert len(ids) == len(set(ids)), twin.name
