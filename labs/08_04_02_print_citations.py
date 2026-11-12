# %%
"""Lab 25.2: print citations on a DataFlow answer.

What we build: you type the small function that turns a passage's metadata into a citation line, and code
prints a Sources block under the create_agent desk's reply from the passages its retrieve tool returned.
Three questions: a refund question from a support lead (every folder), the same question from a customer,
and a price question that cites a row of a csv. Then you break the row on purpose.

What you learn: 25.1's idea made real. A citation is the file and the place in the file, carried as
metadata from the loader through the retrieve tool and printed by code, never written by the model; which
files a desk may cite is decided by the caller's scope. Nothing grades a passage on this desk, so Sources
lists every passage the tool returned, used or not: the limit the grading graph fixes after LangGraph.

What will be true on your screen: five format_sources lines from your function, then for each caller the
tool call, the reply and its Sources block: for the support lead the procedures file and its 6.1 section,
for the customer no internal_operations path, on the price question a billing_and_pricing.csv line ending
in a row number, and one refund citation with its lines. Then python -m pytest tests/test_lab_08_04_02.py -q.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.rag.desk import ask_desk, build_rag_desk, reply_text


# %%
# TYPE THIS: format_sources. The signature and docstring are given; you type the body.
# Its finished copy is format_sources in dataflow/rag/cite.py, which every later desk and graph cites through.
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
# The create_agent desk. Who is asking rides in the envelope, and the retrieve tool reads its scope from there.
from dataflow.rag.cite import format_sources as finished_format_sources, tool_passages

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
desk = build_rag_desk(model=chat)


def ask(question: str, caller: str, actor: str) -> dict:
    print("desk", caller, "actor", actor)
    print("question", question)
    state = ask_desk(desk, question, actor_id=actor, model=chat)
    for message in state["messages"]:
        for call in getattr(message, "tool_calls", None) or []:
            print("tool_call", call["name"], call["args"])
    passages = tool_passages(state["messages"])
    reply = cite({"reply": reply_text(state), "sources": passages})["reply"]
    print(reply)
    return {"reply": reply, "passages": passages}


refund = "Who can approve a refund under 30 days?"
staff = ask(refund, "support_agent", "desk-lead")
customer = ask(refund, "customer", "anon")
print("customer_desk_cites_internal", "internal_operations" in customer["reply"])
price = ask("How much does an extra user cost on the Professional plan?", "support_agent", "desk-lead")
print("price_cites_a_row", " row " in price["reply"].split("Sources:")[-1])


# %%
# One step further: a text file's chunk records the lines it covers, and the finished copy prints them.
lined = [row for row in staff["passages"] if row.get("line_start") is not None]
refund_rows = [row for row in lined if "Refund" in str(row.get("heading_path"))] or lined
print("refund_citation_with_lines", finished_format_sources(refund_rows[:1]) or "none: the tool returned no text passage on this run")
