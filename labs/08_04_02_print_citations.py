# %%
"""Lab 25.2: print citations on a DataFlow answer.

What we build: you type the small function that turns a passage's metadata into a citation line, hand it to
the DataFlow graph as its cite step, and ask three questions: a refund question on the support-agent desk
(scope "all", every folder), the same question on the customer desk, and a price question that cites a row
of a csv. Then you break the row on purpose.

What you learn: 25.1's idea made real. A citation is the file and the place in the file, carried as
metadata from the loader through retrieve and grade and printed by code, never written by the model; the
Sources block lists every passage the grader kept, which is what the answer was allowed to use; and which
files a desk may cite is decided by its scope, not by the question.

What will be true on your screen: five format_sources lines from your function, then for each desk the
grades, the reply and its Sources block: on the support-agent desk the procedures file and its 6.1
section, on the customer desk no internal_operations path, and on the price question a
billing_and_pricing.csv line ending in a row number. Then python -m pytest tests/test_lab_08_04_02.py -q.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.rag_graph import build_rag_graph


# %%
# TYPE THIS: format_sources. The signature and docstring are given; you type the body.
# Its finished copy is format_sources in dataflow/rag/cite.py, the cite step of every later graph.
def format_sources(sources: list) -> str:
    """One line per source: the path, then ' > ' and the heading path when there is one (else h2 > h3), then ' row N' when the source is a csv row; row 0 counts. A plain string passes through stripped; an empty entry is skipped."""
    lines = []
    for item in sources:
        if isinstance(item, str):
            if item.strip():
                lines.append(item.strip())
            continue
        path = str(item.get("source") or "").strip()
        heading = str(item.get("heading_path") or "").strip() or " > ".join(
            part for part in (str(item.get("h2") or "").strip(), str(item.get("h3") or "").strip()) if part
        )
        line = f"{path} > {heading}" if path and heading else path or heading
        row = item.get("row")
        if row is not None and row != "":
            line = f"{line} row {row}"
        if line:
            lines.append(line)
    return "\n".join(lines)


# BREAK: write the row check as
#     if row:
# run the lab and read the price question's Sources line, then python -m pytest tests/test_lab_08_04_02.py -q.
# git checkout -- labs/08_04_02_print_citations.py puts it back.

for sample in (
    [{"source": "dataflow/knowledge_base/business_data/billing_and_pricing.csv", "row": 0}],
    [{"source": "dataflow/wiki/return_policy.md", "h2": "Returns", "h3": "Window"}],
    [{"source": "dataflow/wiki/return_policy.md", "heading_path": "DataFlow return policy", "h2": "ignored"}],
    ["  dataflow/wiki/shipping.md  "],
    [{}],
):
    print("format_sources", sample, "->", repr(format_sources(sample)))


# Given, not typed: the cite step, a copy of cite in dataflow/rag/cite.py that calls your format_sources.
def cite(state: dict) -> dict:
    sources = list(state.get("sources") or [])
    reply = str(state.get("reply") or state.get("answer") or "").rstrip()
    if sources:
        return {"reply": reply + "\n\nSources:\n" + format_sources(sources)}
    return {"reply": reply + "\n\nSources: none (this reply did not use the knowledge base)"}


# %%
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))


def ask(question: str, desk: str, scope: str) -> dict:
    print("desk", desk, "scope", scope)
    print("question", question)
    state = build_rag_graph(model=chat, scope=scope, cite_node=cite).invoke({"question": question})
    for row in state.get("grades") or []:
        print("GRADE", row["label"], row["source"])
    print(state.get("reply"))
    return state


refund = "Who can approve a refund under 30 days?"
staff = ask(refund, "support_agent", "all")
customer = ask(refund, "customer", "customer")
print("customer_desk_cites_internal", "internal_operations" in str(customer.get("reply")))
price = ask("How much does an extra user cost on the Professional plan?", "support_agent", "all")
print("price_cites_a_row", " row " in str(price.get("reply")).split("Sources:")[-1])
