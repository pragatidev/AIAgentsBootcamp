"""Helpers for the MCP lab tests: fake retrieval inside a stdio server child.

A stdio server is a separate process, so monkeypatching retrieve_passages in the test process does not
reach it. fake_retrieval_in_children writes a sitecustomize.py that patches it at the child's start-up
and puts its folder on PYTHONPATH, which dataflow.mcp.client.stdio_env() passes on to every child.
The patch is the one tests/test_rag_desk.py makes in process: one fixed passage, no index, no model.
"""

from __future__ import annotations

from pathlib import Path

PASSAGE = {
    "source": "dataflow/wiki/return_policy.md",
    "folder": "wiki",
    "heading_path": "DataFlow return policy",
    "text": "The customer return window is 30 days from delivery.",
}

SITECUSTOMIZE = f'''"""Written by tests/fixtures/mcp_fixtures.py for one test run. Fakes retrieval in an MCP server child."""
import importlib

_rt = importlib.import_module("dataflow.tools.retrieve")
_rt.retrieve_passages = lambda question, **kwargs: [{PASSAGE!r}]
'''


def fake_retrieval_in_children(tmp_path: Path, monkeypatch) -> Path:
    """Make every stdio child started after this call answer retrieve with PASSAGE. Returns the folder."""
    folder = tmp_path / "child_site"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(folder))
    return folder
