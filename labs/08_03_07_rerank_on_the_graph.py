# %%
"""Lab 24.7, second file: rerank a shortlist on the DataFlow graph. Run this one after LangGraph.

What we build: the error code that dense search ranked worst in labs/08_03_07_hybrid_and_rerank.py goes
through the DataFlow RAG graph twice, with hybrid search and then with hybrid search and a rerank: the
model reads each passage of the shortlist, scores it against the question, and the graph keeps the best.
You see each passage's score, where it stood before, and what the rerank cost in model calls and tokens.

What you learn: a rerank reads a shortlist with the model and costs one call per passage, so it buys a
better order with latency and tokens. It is a step between the search and the answer, which is why it
waits for a graph: the create_agent desk is one loop, with no place to put a step the model cannot skip.
Advanced RAG owns the depth: tuned fusion, cross-encoders, rerank models.

What will be true on your screen: the code dense ranks worst, the model's name, then for each desk its
passages, whether the code's chunk is among them, the reply's Sources, and model_calls and tokens; on the
rerank desk, one rerank line per shortlisted passage with its score, where it stood, and the reason.
Then python -m pytest tests/test_lab_08_03_07_rerank.py -q passes.
"""

from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.rag.faiss_index import search
from dataflow.rag.load import KB_DIR
from dataflow.tools.retrieve import SCOPES, get_index
from eval.runners.rag_metrics import meter


# %%
# The same pick as the first file: the code whose chunk dense search ranks worst.
guide = KB_DIR / "customer_facing" / "troubleshooting_guide.txt"
codes = re.findall(r"^Error Code: (\S+)", guide.read_text(encoding="utf-8"), flags=re.M)
index = get_index(scope="customer")
folders = SCOPES["customer"]


def rank_of(rows: list[dict], code: str) -> int | None:
    """1-based rank of the first chunk that holds this code's block, or None."""
    return next((n for n, row in enumerate(rows, start=1) if f"Error Code: {code}" in row["text"]), None)


def dense_rank(code: str) -> int | None:
    question = f"What does error {code} mean and how do I fix it?"
    return rank_of([row for row in search(index, question, k=40) if row["folder"] in folders][:10], code)


dense = {code: dense_rank(code) for code in codes}
worst = max(codes, key=lambda code: (dense[code] or 99, codes.index(code)))
print("worst_dense_code", worst, "dense", dense[worst])


# %%
# The worst code through the DataFlow customer graph: hybrid, then hybrid with the rerank step.
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
question = f"What does error {worst} mean and how do I fix it?"
print("question", question)
for label, options in (
    ("hybrid", {"retrieve_mode": "hybrid"}),
    ("hybrid_rerank", {"retrieve_mode": "hybrid", "rerank_enabled": True}),
):
    with meter() as used:
        state = build_rag_graph(model=chat, **options).invoke({"question": question})
    passages = state.get("passages") or []
    print("desk", label)
    for row in state.get("reranked") or []:
        print("  rerank", row["score"], row["source"], "| was", row["was"] + 1, "|", row["reason"])
    print("  passages", [Path(p["source"]).name for p in passages])
    print("  code_chunk_retrieved", rank_of(passages, worst) is not None)
    print("  sources", [Path(s["source"]).name for s in state.get("sources") or []])
    print("  reply", str(state.get("answer") or state.get("reply"))[:300].replace("\n", " "))
    print("  model_calls", used.model_calls, "tokens", used.tokens)
