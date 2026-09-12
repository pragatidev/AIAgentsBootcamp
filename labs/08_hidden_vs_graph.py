# %%
"""S8.1 Why a product needs a graph: a hidden loop you cannot test or pause."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.graphs.v1_triage import build_v1_triage, classify

# %%
def hidden_loop(ticket: str) -> str:
    """A while-loop agent. You cannot unit-test classify. You cannot interrupt."""
    text = ticket.lower()
    if "return" in text or "df-" in text:
        step = "lookup"
    else:
        step = "policy"
    return step


print("hidden_step", hidden_loop("Can I return order DF-1001?"))
print("hidden_can_test_classify_alone", False)
print("hidden_can_interrupt", False)

# %%
print("graph_classify", classify({"ticket": "Can I return order DF-1001?"}))
g = build_v1_triage()
print("graph_can_test_classify_alone", True)
print("graph_compiled", True)
print("graph_nodes", sorted(g.get_graph().nodes))
