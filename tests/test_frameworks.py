"""Part 16 framework labs. Rubric structure plus import skips."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUBRIC = ROOT / "labs" / "16_compare" / "rubric.md"

PRODUCTS = [
    "Langflow",
    "n8n",
    "CrewAI",
    "AutoGen",
    "OpenAI Agents SDK",
    "Google ADK",
    "LangGraph",
]
REQUIRED = [
    "product",
    "interrupt",
    "checkpointer",
    "tests",
    "package",
    "human gate",
    "gain",
    "lose",
    "when not",
    "path",
]


def parse_rubric(text: str) -> tuple[list[dict], list[str]]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip().startswith("|")]
    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows, headers


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rubric_has_seven_rows_no_empty_cells_and_a_loss_per_row():
    text = RUBRIC.read_text(encoding="utf-8")
    rows, headers = parse_rubric(text)
    assert "when not" in headers
    for name in REQUIRED:
        assert name in headers
    assert [row["product"] for row in rows] == PRODUCTS
    assert len(rows) == 7
    for row in rows:
        for key, value in row.items():
            assert value != "", "empty cell " + row["product"] + " " + key
        assert row["lose"], "no loss " + row["product"]
        path = ROOT / row["path"]
        assert path.is_file(), row["path"]


def test_run_json_paths_exist():
    text = RUBRIC.read_text(encoding="utf-8")
    rows, _headers = parse_rubric(text)
    for row in rows:
        path = ROOT / row["path"]
        assert path.is_file(), row["path"]


def test_import_langflow_export():
    load_module("lab16_langflow_export", ROOT / "labs" / "16_langflow" / "exported.py")


def test_import_crewai_crew():
    pytest.importorskip(
        "crewai",
        reason="crewai uninstalled from the shared venv after its mcp pin broke FastMCP tests",
    )
    load_module("lab16_crew", ROOT / "labs" / "16_crewai" / "crew.py")


def test_import_autogen_supportflow():
    pytest.importorskip("autogen_agentchat")
    pytest.importorskip("autogen_ext")
    load_module("lab16_supportflow", ROOT / "labs" / "16_autogen" / "supportflow.py")


def test_import_openai_agents_ticket():
    pytest.importorskip("agents", reason="openai-agents is not installed")
    load_module("lab16_openai_ticket", ROOT / "labs" / "16_openai_agents" / "ticket.py")


def test_import_adk_ticket():
    pytest.importorskip("google.adk", reason="google-adk is not installed")
    load_module("lab16_adk_ticket", ROOT / "labs" / "16_adk" / "ticket.py")
