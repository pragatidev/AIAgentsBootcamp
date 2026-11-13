"""Lab 06.04.03 (13.2), THREAD, start and resume typed by the student. start dies with os._exit like a killed process,
so --start and --resume run as two child processes, each with the fixture model (tests/fixtures/lg_r1.py) and a
temp database through DATAFLOW_CHECKPOINTS_PATH. The no-flag cell runs in this process with the fixture model."""

import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

import config
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow, scripted_children

LAB = ROOT / "labs" / "06_04_03_sqlite_kill_and_resume.py"
SAME_THREAD = "    thread = THREAD\n"
OTHER_THREAD = '    thread = {"configurable": {"thread_id": "lab-13-2-other"}}\n'
REPLY = "looked up desk lamp"


def _run(lab: Path, flag: str, db: Path) -> list[str]:
    env = dict(os.environ, DATAFLOW_CHECKPOINTS_PATH=str(db), PYTHONIOENCODING="utf-8")
    proc = subprocess.run([sys.executable, str(lab), flag], capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc.stdout.splitlines()


def _pid(lines: list[str]) -> str:
    return next(line.split()[1] for line in lines if line.startswith("process "))


def test_no_flag_runs_the_thread_in_memory(monkeypatch, capsys):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="orders", reply=REPLY))
    monkeypatch.setattr(sys, "argv", ["06_04_03_sqlite_kill_and_resume.py"])
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert any(line.startswith("memory turn 1 turns 1 checkpoints ") for line in out)
    assert any(line.startswith("memory turn 2 turns 2 checkpoints ") for line in out)
    assert f"fresh thread turns 1 reply {REPLY}" in out
    assert out[-1].startswith("next: python labs/06_04_03_sqlite_kill_and_resume.py --start")


def test_start_dies_and_a_second_process_resumes(tmp_path, monkeypatch):
    scripted_children(tmp_path, monkeypatch, "orders")
    db = tmp_path / "checkpoints.sqlite"
    started = _run(LAB, "--start", db)
    assert started[-1].endswith("dies now")
    assert any(line.endswith(f"turn 1 turns 1 reply {REPLY}") for line in started)
    assert not any(line.startswith("memory ") for line in started)
    resumed = _run(LAB, "--resume", db)
    assert _pid(started) != _pid(resumed)
    assert any(line.endswith(f"saved turns 1 reply {REPLY}") for line in resumed)
    rows = int(next(line.split()[1] for line in resumed if line.startswith("rows_in_file ")))
    assert rows > 0
    assert resumed[-1] == f"turn 2 turns 2 reply {REPLY}"


def test_break_other_thread_answers_as_a_stranger(tmp_path, monkeypatch):
    scripted_children(tmp_path, monkeypatch, "orders")
    broken = lab_copy_dataflow(LAB, tmp_path, SAME_THREAD, OTHER_THREAD)
    db = tmp_path / "checkpoints.sqlite"
    _run(broken, "--start", db)
    resumed = _run(broken, "--resume", db)
    assert any(line.endswith("saved turns None reply None") for line in resumed)
    assert "rows_in_file 0" in resumed
    assert resumed[-1] == f"turn 2 turns 1 reply {REPLY}"
