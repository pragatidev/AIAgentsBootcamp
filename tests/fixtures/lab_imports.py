"""Which imports of a lab name a graph: LangGraph itself, or a module under dataflow/graphs."""

from __future__ import annotations

import ast
from pathlib import Path

GRAPH_PREFIXES = ("langgraph", "dataflow.graphs", "eval.runners")


def graph_imports(lab: Path) -> list[str]:
    """Every module the file imports, at any depth, that is LangGraph, a DataFlow graph, or a runner that builds one."""
    found: list[str] = []
    for node in ast.walk(ast.parse(lab.read_text(encoding="utf-8"))):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        found += [name for name in names if name.startswith(GRAPH_PREFIXES)]
    return sorted(found)
