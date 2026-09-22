"""Every graph langgraph.json serves must import, and a lab must send the student to the graph it ran.

Written 2026-09-22 after a real defect: labs/09_02_05_studio_replay.py told the student to open
Studio, pick the desk graph and find the thread from the terminal run. The desk graph is v4_hitl
(classify, lookup, policy, refund), the lab runs the RAG graph, and the terminal thread lives in an
InMemorySaver inside that process, so the server had never heard of it. Nothing the student did
could work. Naming a served graph is not enough, which is why the second test compares the graph the
lab names against the module the lab imports.
"""

from __future__ import annotations

import json
import re
from importlib import import_module
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "langgraph.json").read_text(encoding="utf-8"))
GRAPHS = CONFIG["graphs"]
PICKS = re.compile(r"pick the (\w[\w-]*) graph", re.I)


def module_of(target: str) -> str:
    return target.partition(":")[0].lstrip("./").removesuffix(".py").replace("/", ".")


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_every_served_graph_imports(name: str) -> None:
    """A graph named in langgraph.json must exist, or `langgraph dev` serves a broken menu."""
    target = GRAPHS[name]
    obj = getattr(import_module(module_of(target)), target.partition(":")[2])
    assert hasattr(obj, "get_graph"), f"{name} -> {target} is not a compiled graph"


def test_a_lab_names_the_graph_it_actually_runs() -> None:
    """A lab that sends the student to Studio must send them to the graph it ran."""
    wrong = []
    for lab in sorted((ROOT / "labs").glob("*.py")):
        text = lab.read_text(encoding="utf-8", errors="replace")
        for named in sorted(set(PICKS.findall(text))):
            target = GRAPHS.get(named.lower())
            if target is None:
                wrong.append(f"{lab.name}: says 'pick the {named} graph', which langgraph.json does not serve")
                continue
            module = module_of(target)
            if not re.search(r"(from|import)\s+" + re.escape(module), text):
                wrong.append(
                    f"{lab.name}: says 'pick the {named} graph' ({module}), but the lab never imports that "
                    f"module, so the student opens a different graph than the one this lab ran"
                )
    assert wrong == [], "; ".join(wrong)
