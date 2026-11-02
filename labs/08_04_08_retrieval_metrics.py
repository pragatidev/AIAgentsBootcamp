# %%
"""Lab 25.8: measure retrieval alone, recall at k and MRR, and the golden set behind it.

What we build: you type the function that scores one question's retrieval: where the expected file ranks in
the top five passages, recall at 1, 3 and 5, and MRR. The twelve DataFlow questions then go through the
support-agent desk's retrieve with the embedder and no chat model, dense first and then hybrid, and you read
the table beside the one number Section 25.5 printed for retrieval.

What you learn: retrieval is a stage you can measure without a model in the loop, cheaply and the same on
every run for a fixed index. A rank metric says how high the right file sits, not just whether it showed
up. And a metric must leave out what it cannot score: the five refuse and lookup rows name no file, so
they are left out, never counted as hits; 25.5's context_recall counts them as 1 by definition, and Section
29's floors gate on that one as it is. eval/QUESTIONS.md writes down why each row exists.

What will be true on your screen: one line per scored row (its rank and the four numbers) for dense and for
hybrid, the means over the seven rows that name a file, rows_left_out 5, and context_recall_by_definition 5
of 12. Then python -m pytest tests/test_lab_08_04_08.py -q passes.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from eval.runners.rag_metrics import load_questions, mean, run_retrieval_only


# %%
# TYPE THIS: retrieval_metrics. The signature and docstring are given; you type the body.
# Its finished copy is retrieval_metrics in eval/runners/rag_metrics.py.
def retrieval_metrics(row: dict, passages: list[dict], ks: tuple = (1, 3, 5)) -> dict | None:
    """For a row that names an expected file: its 0-based rank among the passages (None when absent), recall_at_k for each k (1 when the rank is below k) and mrr (1 / (rank + 1), or 0). A row with no expected_source returns None: left out, never counted as a hit."""
    expected = str(row.get("expected_source") or "").replace("\\", "/")
    if not expected:
        return None
    sources = [str(p.get("source") or "").replace("\\", "/") for p in passages]
    rank = sources.index(expected) if expected in sources else None
    out = {"id": row.get("id"), "rank": rank}
    for k in ks:
        out[f"recall_at_{k}"] = 1 if rank is not None and rank < k else 0
    out["mrr"] = 0.0 if rank is None else 1.0 / (rank + 1)
    return out


# BREAK: score the rows that name no file as perfect hits. Replace "return None" with
#         return {"id": row.get("id"), "rank": 0, "recall_at_1": 1, "recall_at_3": 1, "recall_at_5": 1, "mrr": 1.0}
# run the lab and read the means, then python -m pytest tests/test_lab_08_04_08.py -q.
# git checkout -- labs/08_04_08_retrieval_metrics.py puts it back.


# %%
embeddings = config.get_embeddings()
print("embedder", type(embeddings).__name__, getattr(embeddings, "model", None) or getattr(embeddings, "model_name", None))
print("chat_model none: this lab never calls one")
rows = load_questions()


def table(mode: str) -> dict:
    scored = []
    for row in rows:
        result = retrieval_metrics(row, run_retrieval_only(row["question"], k=5, scope="support_agent", mode=mode))
        if result is None:
            continue
        scored.append(result)
        print(mode, result["id"], "rank", result["rank"], "recall_at_1", result["recall_at_1"], "recall_at_3", result["recall_at_3"],
              "recall_at_5", result["recall_at_5"], "mrr", round(result["mrr"], 3))
    means = {key: round(mean([r[key] for r in scored]), 3) for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr")}
    print(mode, "means over", len(scored), "rows", means)
    print(mode, "rows_left_out", len(rows) - len(scored))
    return means


dense = table("dense")
try:
    hybrid = table("hybrid")
except ImportError as err:
    print("hybrid skipped:", err)


# %%
print("context_recall_by_definition", sum(1 for row in rows if not row.get("expected_source")), "of", len(rows))
print("one_scored_row_moves_a_mean_by", round(1 / max(1, sum(1 for row in rows if row.get("expected_source"))), 3))
