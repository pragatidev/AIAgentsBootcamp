"""Helpers for the LangGraph opening and routing lab tests (LG-R1, Sections 9 to 11).

lab_copy_dataflow: the house lab_copy, plus the DataFlow tickets file the copy reads through its own root.
scripted_children: a lab that starts child processes (9.4's kill-and-resume probe) cannot be reached by a
monkeypatch in the test process, so this writes a sitecustomize.py that swaps config.get_chat_model for the
fixture model at each child's start-up and puts its folder, and the repo root, on PYTHONPATH.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from tests.fixtures.lab_copy import ROOT, lab_copy

SITECUSTOMIZE = '''"""Written by tests/fixtures/lg_r1.py for one test run. The fixture model in a lab's child process."""
import config


def _scripted(**kwargs):
    from tests.fixtures.fake_model import FakeChatModel

    return FakeChatModel(route={route!r})


config.get_chat_model = _scripted
'''


def lab_copy_dataflow(lab: Path, tmp_path: Path, old: str, new: str) -> Path:
    """lab_copy with old replaced by new, and dataflow/data/tickets.jsonl beside it."""
    copy = lab_copy(lab, tmp_path, old, new)
    data = tmp_path / "dataflow" / "data"
    data.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "dataflow" / "data" / "tickets.jsonl", data / "tickets.jsonl")
    return copy


def scripted_children(tmp_path: Path, monkeypatch, route: str) -> Path:
    """Every Python child started after this call gets FakeChatModel(route=route) from config. Returns the folder."""
    folder = tmp_path / "child_site"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sitecustomize.py").write_text(SITECUSTOMIZE.format(route=route), encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", f"{folder}{os.pathsep}{ROOT}")
    return folder
