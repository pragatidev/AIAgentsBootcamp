"""Lab 06.00.03 (9.3), the smallest graph. No model anywhere, so the lab runs here exactly as on a student's machine."""

import runpy
from importlib.metadata import version
from pathlib import Path

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_00_03_smallest_graph.py"

T1 = "{'ticket': 'Where is order DF-1002?', 'note': 'classify saw an order; reply answered'}"
T2 = "{'ticket': 'What is your return window?', 'note': 'classify saw a question; reply answered'}"
DRAWING = [
    "---",
    "config:",
    "  flowchart:",
    "    curve: linear",
    "---",
    "graph TD;",
    "\t__start__([<p>__start__</p>]):::first",
    "\tclassify(classify)",
    "\treply(reply)",
    "\t__end__([<p>__end__</p>]):::last",
    "\t__start__ --> classify;",
    "\tclassify --> reply;",
    "\treply --> __end__;",
    "\tclassDef default fill:#f2f0ff,line-height:1.2",
    "\tclassDef first fill-opacity:0",
    "\tclassDef last fill:#bfb6fc",
    "",
]
EXPECTED = [
    "model none: this run calls no model",
    f"langchain-core {version('langchain-core')}",
    f"langgraph {version('langgraph')}",
    "nodes ['__start__', 'classify', 'reply', '__end__']",
    *DRAWING,
    f"t1 final {T1}",
    f"t1 saved {T1}",
    "t1 next ()",
    "t1 checkpoint step -1 next ('__start__',) values {}",
    "t1 checkpoint step 0 next ('classify',) values {'ticket': 'Where is order DF-1002?'}",
    "t1 checkpoint step 1 next ('reply',) values {'ticket': 'Where is order DF-1002?', 'note': 'classify saw an order'}",
    f"t1 checkpoint step 2 next () values {T1}",
    "t1 checkpoints 4",
    f"t2 final {T2}",
    f"t2 saved {T2}",
    f"t1 saved again {T1}",
    "threads share state False",
]


def test_every_printed_line(capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    assert capsys.readouterr().out.splitlines() == EXPECTED


def test_the_two_threads_are_two_notebooks():
    lab = runpy.run_path(str(LAB), run_name="__main__")
    graph = lab["graph"]
    t1 = graph.get_state({"configurable": {"thread_id": "t1"}})
    t2 = graph.get_state({"configurable": {"thread_id": "t2"}})
    assert t1.values["ticket"] != t2.values["ticket"]
    assert t1.config["configurable"]["thread_id"] == "t1"
    assert t2.config["configurable"]["thread_id"] == "t2"
    assert graph.get_state({"configurable": {"thread_id": "t3"}}).values == {}
