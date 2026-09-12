"""18.x career and business pages. No currency. No income claim words."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGES = [
    "career/pm/spec.md",
    "career/pm/metrics.md",
    "career/pm/gate_policy.md",
    "career/pm/cost_model.md",
    "career/pm/demo_script.md",
    "career/qa/test_plan.md",
    "business/offer.md",
    "business/price.md",
    "business/saas_replace.md",
]

PLAN_PATHS = [
    "tests/test_nodes_dataflow.py",
    "eval/golden.jsonl",
    "eval/load/replay.py",
    "eval/runners/faithfulness.py",
    "eval/ui/test_dataflow_chat.py",
]

TOOLS = (
    "lookup_order",
    "search_policy",
    "issue_refund",
    "decline_refund",
)

BANNED = re.compile(r"\b(earn|income|revenue|profit|guaranteed)\b", re.I)
CURRENCY = re.compile(r"[$€£¥₹¢]")


def test_every_page_exists():
    for rel in PAGES:
        path = ROOT / rel
        assert path.is_file(), rel


def test_no_currency_or_banned_word_under_career_or_business():
    roots = [ROOT / "career", ROOT / "business"]
    files: list[Path] = []
    for folder in roots:
        assert folder.is_dir(), folder
        files.extend(
            p
            for p in folder.rglob("*")
            if p.is_file() and p.suffix in {".md", ".py"}
        )
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        assert not CURRENCY.search(text), "currency in " + rel
        hit = BANNED.search(text)
        assert hit is None, "banned " + hit.group(1) + " in " + rel


def test_test_plan_rows_point_at_existing_paths():
    text = (ROOT / "career" / "qa" / "test_plan.md").read_text(encoding="utf-8")
    for rel in PLAN_PATHS:
        assert rel in text, rel
        assert (ROOT / rel).is_file(), rel


def test_spec_names_four_tools_with_read_or_write():
    text = (ROOT / "career" / "pm" / "spec.md").read_text(encoding="utf-8")
    lower = text.lower()
    for tool in TOOLS:
        assert tool in text, tool
    assert "read" in lower
    assert "write" in lower
    for tool in ("lookup_order", "search_policy"):
        block = _row_for(text, tool)
        assert "read" in block.lower(), tool
    for tool in ("issue_refund", "decline_refund"):
        block = _row_for(text, tool)
        assert "write" in block.lower(), tool


def _row_for(text: str, tool: str) -> str:
    for line in text.splitlines():
        if tool in line:
            return line
    return ""
