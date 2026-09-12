"""7.1 harness parts. Pytest stays green with no live model."""

from pathlib import Path
import re

from dataflow.agent.harness_loop import run_desk
from dataflow.tools import refund as refund_mod
from tests.fixtures.fake_model import FakeChatModel

ROOT = Path(__file__).resolve().parents[1]


def test_parts_md_names_existing_files():
    text = (ROOT / "harness" / "parts.md").read_text(encoding="utf-8")
    assert "## Tools" in text
    assert "## Context policy" in text
    assert "## Permissions" in text
    assert "## Stop rules" in text
    assert "none yet, Section 21" in text
    paths = re.findall(r"([A-Za-z0-9_./-]+\.(?:py|md))", text)
    assert paths
    missing = []
    for raw in paths:
        rel = raw.lstrip("`").rstrip("`")
        if rel.startswith("http"):
            continue
        path = ROOT / rel
        if not path.exists():
            missing.append(rel)
    assert missing == []


def test_capped_loop_stops_with_stopped(tmp_path, monkeypatch, capsys):
    path = tmp_path / "refunds.jsonl"
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(path))
    monkeypatch.setattr(refund_mod, "REFUNDS_PATH", path)
    model = FakeChatModel(
        structured={
            "DeskAction": {
                "tool": "lookup_order",
                "order_id": "DF-1010",
                "amount": 0.0,
                "reason": "",
            }
        }
    )
    out = run_desk(
        "You billed me twice for order DF-1010. Please reverse the extra charge.",
        model=model,
        max_steps=3,
        cap_enabled=True,
    )
    captured = capsys.readouterr()
    assert "STOPPED" in captured.out
    assert out["stop_reason"] == "max_steps"
    assert out["stopped_line"].startswith("STOPPED")
    assert len(out["steps"]) == 3
    assert all(step["proposal"]["tool"] == "lookup_order" for step in out["steps"])
