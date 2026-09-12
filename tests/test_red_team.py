"""11.2 red-team suite. Three rows, fixture blocks, skip is a FAIL."""

import os
from pathlib import Path

from eval.runners.red_team import load_red_team, run_red_team
from tests.test_eval_ci import _load_eval_ci

ROOT = Path(__file__).resolve().parents[1]


def test_three_red_team_rows_load():
    rows = load_red_team()
    assert len(rows) == 3
    kinds = {str(row.get("kind")) for row in rows}
    assert kinds == {"injection", "unscoped", "confirm_bypass"}
    for row in rows:
        assert row.get("must_block")


def test_fixture_run_blocks_all_three(tmp_path):
    dest = tmp_path / "suite.json"
    report = run_red_team(fixture=True, dest=dest)
    assert report["summary"]["n"] == 3
    assert report["summary"]["all_blocked"] is True
    assert all(item["blocked"] for item in report["entries"])


def test_eval_ci_exits_1_on_skipped_red_team():
    mod = _load_eval_ci()
    code = mod.main(["--fixture", "--skip-red-team"])
    assert code == 1
