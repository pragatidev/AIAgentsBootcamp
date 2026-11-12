# %%
"""Lab 24.7: find a DataFlow error code with hybrid search and a rerank.

What we build: the DataFlow troubleshooting guide lists its errors by code. For every code in it, we ask
"What does error <code> mean and how do I fix it?" and print where the chunk holding that code ranks three
ways: dense search (the embedding), BM25 keyword search, and the two fused by reciprocal rank, the ten
lines you type. Then the code dense search ranked worst goes to the create_agent desk twice, its retrieve
tool searching dense and then hybrid, with the model calls and tokens each run cost.

What you learn: an embedding puts meaning in a vector, so an exact token like an error code can sit far
from its question, while keyword search scores the exact word; fusing by rank needs no shared score scale.
The search mode is the deployment's switch, never the model's. The rerank, a model reading a shortlist, is
labs/08_03_07_rerank_on_the_graph.py, for after LangGraph. Advanced RAG owns the depth of both.

What will be true on your screen: one probe line per code with its three ranks (None when not in the top
ten), the code dense ranks worst, then for that code each desk's search rank, tool call and passages,
whether the code's chunk is among them, the reply, and model_calls and tokens per run. Then
python -m pytest tests/test_lab_08_03_07.py -q passes.
"""

from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.rag.cite import tool_passages
from dataflow.rag.desk import ask_desk, build_rag_desk, reply_text
from dataflow.rag.faiss_index import search
from dataflow.rag.hybrid import RRF_K, bm25_for_index, bm25_rows, row_key
from dataflow.rag.load import KB_DIR
from dataflow.tools.retrieve import SCOPES, get_index, retrieve_passages


# %%
# TYPE THIS: reciprocal_rank_fusion. The signature and docstring are given; you type the body.
# Its finished copy is in dataflow/rag/hybrid.py, which the retrieve tool's hybrid search uses.
def reciprocal_rank_fusion(ranked_lists: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """Fuse ranked lists: each chunk scores the sum of 1 / (k + rank) over the lists it is in, rank counted from 1. A chunk in two lists is one row. Return the rows best first, each with its "rrf" score."""
    fused = {}
    for ranked in ranked_lists:
        for rank, row in enumerate(ranked, start=1):
            key = row_key(row)
            if key not in fused:
                fused[key] = {**row, "rrf": 0.0}
            fused[key]["rrf"] += 1.0 / (k + rank)
    return sorted(fused.values(), key=lambda row: -row["rrf"])


# BREAK: drop the constant, so a list's first row outweighs everything below it. Change the signature's
# k: int = RRF_K to k: int = 0, run the lab, then python -m pytest tests/test_lab_08_03_07.py -q.
# git checkout -- labs/08_03_07_hybrid_and_rerank.py puts it back.


# %%
guide = KB_DIR / "customer_facing" / "troubleshooting_guide.txt"
codes = re.findall(r"^Error Code: (\S+)", guide.read_text(encoding="utf-8"), flags=re.M)
print("codes_in_guide", len(codes))
index = get_index(scope="customer")
keywords = bm25_for_index(index)
folders = SCOPES["customer"]


def rank_of(rows: list[dict], code: str) -> int | None:
    """1-based rank of the first chunk that holds this code's block, or None."""
    return next((n for n, row in enumerate(rows, start=1) if f"Error Code: {code}" in row["text"]), None)


ranks = {}
for code in codes:
    question = f"What does error {code} mean and how do I fix it?"
    dense = [row for row in search(index, question, k=40) if row["folder"] in folders][:10]
    keyword = bm25_rows(keywords, question, 10, folders)
    fused = reciprocal_rank_fusion([dense, keyword])[:10]
    ranks[code] = (rank_of(dense, code), rank_of(keyword, code), rank_of(fused, code))
    print("probe", code, "dense", ranks[code][0], "bm25", ranks[code][1], "fused", ranks[code][2])

worst = max(codes, key=lambda code: (ranks[code][0] or 99, codes.index(code)))
print("worst_dense_code", worst, "dense", ranks[worst][0], "bm25", ranks[worst][1], "fused", ranks[worst][2])


# %%
# The worst code on the create_agent desk, twice: the retrieve tool searching dense, then hybrid.
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
question = f"What does error {worst} mean and how do I fix it?"
print("question", question)
for mode in ("dense", "hybrid"):
    print("desk", mode)
    print("  search_rank_of_code_chunk", rank_of(retrieve_passages(question, mode=mode), worst))
    state = ask_desk(build_rag_desk(model=chat, mode=mode), question, model=chat)
    turns = [message for message in state["messages"] if message.type == "ai"]
    for call in [call for message in turns for call in message.tool_calls]:
        print("  tool_call", call["name"], call["args"])
    passages = tool_passages(state["messages"])
    print("  passages", [Path(p["source"]).name for p in passages])
    print("  code_chunk_retrieved", rank_of(passages, worst) is not None)
    print("  reply", reply_text(state)[:300].replace("\n", " "))
    print("  model_calls", len(turns), "tokens", sum((message.usage_metadata or {}).get("total_tokens", 0) for message in turns))
