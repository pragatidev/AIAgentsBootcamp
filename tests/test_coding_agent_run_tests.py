"""15.2 coding desk run_tests never reads a stale .pyc. No live model."""

from __future__ import annotations

import os

from techcorp.harness import coding_agent
from tests.test_sandboxed_loop import BROKEN, FIXED, TEST_SRC


def test_same_size_edit_in_the_same_second_is_not_stale(tmp_path, monkeypatch):
    # The flaky case, pinned: FIXED has BROKEN's length, and the mtime is set
    # back to BROKEN's so a cached .pyc would still look current.
    box = tmp_path / "sandbox"
    box.mkdir()
    fixture = box / "fixture.py"
    fixture.write_text(BROKEN, encoding="utf-8")
    (box / "test_fixture.py").write_text(TEST_SRC, encoding="utf-8")
    monkeypatch.setattr(coding_agent, "SANDBOX_ROOT", box)
    broken_mtime = fixture.stat().st_mtime
    assert coding_agent._run_tests()["passed"] is False
    fixture.write_text(FIXED, encoding="utf-8")
    os.utime(fixture, (broken_mtime, broken_mtime))
    assert coding_agent._run_tests()["passed"] is True
