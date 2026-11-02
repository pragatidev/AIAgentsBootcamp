"""Naive vs agentic RAG metrics on eval/questions.jsonl.

Faithfulness is an LLM judge: every claim in the answer appears in the
cited passages (0 or 1). Context recall is whether the expected source
was retrieved. Refused correctly is a refuse row that actually refused.
Tokens and model calls are counted per question, inside each pipeline only
(the judge's calls are not counted). retrieval_metrics measures retrieval
alone, with no chat model: the rank of the expected file, recall at k, MRR.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tracers.context import register_configure_hook

from config import ROOT, get_chat_model
from dataflow.graphs.rag_graph import build_rag_graph, generate
from dataflow.rag.faiss_index import search
from dataflow.tools.retrieve import get_index

QUESTIONS = ROOT / "eval" / "questions.jsonl"


class CallMeter(BaseCallbackHandler):
    """Counts chat model calls and sums their tokens, from every call made inside meter()."""

    def __init__(self) -> None:
        super().__init__()
        self.model_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self.model_calls += 1
        for generations in getattr(response, "generations", None) or []:
            for generation in generations:
                usage = getattr(getattr(generation, "message", None), "usage_metadata", None) or {}
                self.input_tokens += int(usage.get("input_tokens") or 0)
                self.output_tokens += int(usage.get("output_tokens") or 0)

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


_METER: ContextVar[CallMeter | None] = ContextVar("rag_call_meter", default=None)
register_configure_hook(_METER, inheritable=True)


@contextmanager
def meter():
    """Every LangChain chat model call inside this block reports to the CallMeter it yields."""
    handler = CallMeter()
    token = _METER.set(handler)
    try:
        yield handler
    finally:
        _METER.reset(token)

JUDGE_SYSTEM = (
    "You judge faithfulness. The answer may only use facts that appear "
    "in the passages. If every claim in the answer appears in the passages, "
    "reply 1. If the answer adds a policy, number, or fact that is not in "
    "the passages, reply 0. If the answer is a refusal and the passages "
    "do not answer the question, reply 1. Reply with 0 or 1 only."
)


def load_questions(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or QUESTIONS
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _source_blob(sources: list[Any]) -> str:
    parts: list[str] = []
    for item in sources:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            parts.append(str(item.get("source") or ""))
    return " ".join(parts).replace("\\", "/")


def _refused(text: str) -> bool:
    return "I do not have that in the knowledge base" in (text or "")


def refusal_scores(kind: str, answer: str, passages: list, *, judge, model: Any = None) -> dict[str, Any]:
    """Score one answer on refusal.

    refused is True only when the answer carries the house refusal sentence. A
    refuse row that refused: refused_correctly 1, faithfulness 1, no judge call. A
    refuse row that answered: refused_correctly 0, faithfulness from the judge,
    fluent_miss True when the answer is not empty. Any other row: a refusal scores
    faithfulness 1 and over_refusal True; an answer goes to the judge.
    """
    refused = _refused(answer)
    if kind == "refuse":
        refused_correctly = 1 if refused else 0
        faithful = 1 if refused else judge(answer, passages, model=model)
    elif refused:
        refused_correctly = 0
        faithful = 1
    else:
        refused_correctly = 0
        faithful = judge(answer, passages, model=model)
    return {
        "refused": refused,
        "refused_correctly": refused_correctly,
        "faithfulness": faithful,
        "fluent_miss": kind == "refuse" and not refused and bool(answer.strip()),
        "over_refusal": kind != "refuse" and refused,
    }


def retrieval_metrics(row: dict[str, Any], passages: list[dict[str, Any]], ks: tuple[int, ...] = (1, 3, 5)) -> dict[str, Any] | None:
    """Retrieval alone, for a row that names an expected file: its 0-based rank, recall at each k, and MRR.

    rank is the position of the first passage whose source is the expected file,
    None when it is not there. recall_at_k is 1 when the rank is below k. mrr is
    1 / (rank + 1), or 0. A row with no expected_source (refuse, lookup) returns
    None: it is left out, never counted as a hit.
    """
    expected = str(row.get("expected_source") or "").replace("\\", "/")
    if not expected:
        return None
    sources = [str(p.get("source") or "").replace("\\", "/") for p in passages]
    rank = sources.index(expected) if expected in sources else None
    out: dict[str, Any] = {"id": row.get("id"), "rank": rank}
    for k in ks:
        out[f"recall_at_{k}"] = 1 if rank is not None and rank < k else 0
    out["mrr"] = 0.0 if rank is None else 1.0 / (rank + 1)
    return out


def run_retrieval_only(question: str, *, k: int = 5, index: Any = None, scope: str = "support_agent", **retrieve_kwargs: Any) -> list[dict[str, Any]]:
    """The top k passages for a question, with the embedder and no chat model. index= searches that index directly."""
    if index is not None:
        return search(index, question, k=k, folder=None)
    from dataflow.tools.retrieve import retrieve_passages

    return retrieve_passages(question, k=k, scope=scope, **retrieve_kwargs)


def retrieval_table(rows: list[dict[str, Any]], passages_for: Callable[[str], list[dict[str, Any]]], ks: tuple[int, ...] = (1, 3, 5)) -> dict[str, Any]:
    """retrieval_metrics for every row that names a file, and their means. Rows with no file are counted, not scored."""
    scored = []
    for row in rows:
        result = retrieval_metrics(row, passages_for(str(row.get("question") or "")), ks)
        if result is not None:
            scored.append(result)
    means = {f"recall_at_{k}": mean([r[f"recall_at_{k}"] for r in scored]) for k in ks}
    means["mrr"] = mean([r["mrr"] for r in scored])
    return {"rows": scored, "means": means, "scored": len(scored), "left_out": len(rows) - len(scored)}


def faithfulness_judge(
    answer: str,
    passages: list[dict[str, Any]],
    *,
    model: Any = None,
) -> int:
    chat = model or get_chat_model()
    blob = "\n\n".join(
        f"Source: {row.get('source')}\n{row.get('text')}" for row in passages
    )
    result = chat.invoke(
        [
            {"role": "system", "content": JUDGE_SYSTEM},
            {
                "role": "user",
                "content": f"Passages:\n{blob or '(none)'}\n\nAnswer:\n{answer}",
            },
        ]
    )
    content = getattr(result, "content", result)
    if isinstance(content, list):
        content = " ".join(
            str(block.get("text") if isinstance(block, dict) else block)
            for block in content
        )
    text = str(content or "").strip()
    for char in text:
        if char == "1":
            return 1
        if char == "0":
            return 0
    return 0


def run_naive(
    question: str,
    *,
    model: Any = None,
    index: Any = None,
) -> dict[str, Any]:
    store = index if index is not None else get_index(scope="all")
    hits = search(store, question, k=3, folder=None)
    state = generate(
        {"question": question, "graded": hits},
        model=model,
    )
    return {
        "answer": state.get("reply") or state.get("answer") or "",
        "sources": state.get("sources") or [],
        "passages": hits,
        "refused": False,
        "route": "naive",
    }


def run_agentic(
    question: str,
    *,
    model: Any = None,
    graph: Any = None,
) -> dict[str, Any]:
    app = graph or build_rag_graph(model=model, scope="all")
    started = time.perf_counter()
    state = app.invoke({"question": question})
    latency = time.perf_counter() - started
    reply = str(state.get("reply") or state.get("answer") or "")
    return {
        "answer": reply,
        "sources": state.get("sources") or [],
        "passages": state.get("passages") or [],
        "refused": _refused(reply),
        "route": state.get("route"),
        "latency": latency,
        "state": state,
    }


def score_row(
    row: dict[str, Any],
    result: dict[str, Any],
    *,
    judge: Callable[..., int] | None = None,
    model: Any = None,
) -> dict[str, Any]:
    judge = judge or faithfulness_judge
    answer = str(result.get("answer") or "")
    passages = list(result.get("passages") or [])
    sources = _source_blob(result.get("sources") or []) + " " + _source_blob(passages)
    expected = str(row.get("expected_source") or "")
    kind = str(row.get("kind") or "")
    if expected:
        recall = 1 if expected.replace("\\", "/") in sources else 0
    else:
        recall = 1 if kind in {"refuse", "lookup"} else 0
    scores = refusal_scores(kind, answer, passages, judge=judge, model=model)
    return {
        "id": row.get("id"),
        "kind": kind,
        "faithfulness": scores["faithfulness"],
        "context_recall": recall,
        "refused_correctly": scores["refused_correctly"],
        "fluent_miss": scores["fluent_miss"],
        "answer": answer,
        "route": result.get("route"),
    }


def mean(values: list[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def run_metrics(
    path: Path | None = None,
    *,
    model: Any = None,
    judge: Callable[..., int] | None = None,
    naive_fn: Callable[..., dict[str, Any]] | None = None,
    agentic_fn: Callable[..., dict[str, Any]] | None = None,
    index: Any = None,
) -> dict[str, Any]:
    rows = load_questions(path)
    naive_fn = naive_fn or (lambda q: run_naive(q, model=model, index=index))
    if agentic_fn is None:
        graph = build_rag_graph(model=model, scope="all")

        def agentic_fn(q: str, _graph=graph) -> dict[str, Any]:
            return run_agentic(q, model=model, graph=_graph)

    report = {"naive": [], "agentic": []}
    for row in rows:
        question = str(row.get("question") or "")
        t0 = time.perf_counter()
        with meter() as naive_meter:
            naive_result = naive_fn(question)
        naive_result["latency"] = naive_result.get("latency") or (
            time.perf_counter() - t0
        )
        t1 = time.perf_counter()
        with meter() as agentic_meter:
            agentic_result = agentic_fn(question)
        agentic_result["latency"] = agentic_result.get("latency") or (
            time.perf_counter() - t1
        )
        naive_score = score_row(row, naive_result, judge=judge, model=model)
        agentic_score = score_row(row, agentic_result, judge=judge, model=model)
        naive_score["latency"] = naive_result["latency"]
        agentic_score["latency"] = agentic_result["latency"]
        for score, used, result in ((naive_score, naive_meter, naive_result), (agentic_score, agentic_meter, agentic_result)):
            score["tokens"] = int(result.get("tokens", used.tokens))
            score["model_calls"] = int(result.get("model_calls", used.model_calls))
        report["naive"].append(naive_score)
        report["agentic"].append(agentic_score)
    return report


def summarize(report: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in ("naive", "agentic"):
        rows = report[name]
        out.append(
            {
                "pipeline": name,
                "faithfulness": mean([int(r["faithfulness"]) for r in rows]),
                "context_recall": mean([int(r["context_recall"]) for r in rows]),
                "refused_correctly": mean(
                    [
                        int(r["refused_correctly"])
                        for r in rows
                        if r["kind"] == "refuse"
                    ]
                ),
                "latency_s": mean([float(r["latency"]) for r in rows]),
                "fluent_misses": sum(1 for r in rows if r.get("fluent_miss")),
                "tokens_per_q": mean([int(r.get("tokens") or 0) for r in rows]),
                "calls_per_q": mean([int(r.get("model_calls") or 0) for r in rows]),
            }
        )
    return out


def cost_line(input_tokens: int, output_tokens: int) -> str:
    """A cost only when the student has set both prices from their provider's page; the repo holds no price."""
    from config import PRICE_PER_MTOK_IN, PRICE_PER_MTOK_OUT

    if PRICE_PER_MTOK_IN is None or PRICE_PER_MTOK_OUT is None:
        return "cost n/a (local model, no per-token price)"
    dollars = input_tokens / 1_000_000 * PRICE_PER_MTOK_IN + output_tokens / 1_000_000 * PRICE_PER_MTOK_OUT
    return f"cost {dollars:.6f} at your prices ({PRICE_PER_MTOK_IN} in, {PRICE_PER_MTOK_OUT} out per million tokens)"


def render(report: dict[str, list[dict[str, Any]]]) -> str:
    lines: list[str] = []
    lines.append(
        "pipeline  faithfulness  context_recall  refused_correctly  latency_s  fluent_misses  tokens_per_q  calls_per_q"
    )
    for row in summarize(report):
        lines.append(
            f"{row['pipeline']:<9} {row['faithfulness']:.2f}          "
            f"{row['context_recall']:.2f}            "
            f"{row['refused_correctly']:.2f}               "
            f"{row['latency_s']:.2f}       {row['fluent_misses']}"
            f"              {row['tokens_per_q']:.0f}          {row['calls_per_q']:.1f}"
        )
    lines.append("")
    lines.append("per_row")
    for name in ("naive", "agentic"):
        for row in report[name]:
            mark = " FLUENT_MISS" if row.get("fluent_miss") else ""
            lines.append(
                f"{name} {row['id']} kind={row['kind']} "
                f"faith={row['faithfulness']} recall={row['context_recall']} "
                f"refuse={row['refused_correctly']} route={row.get('route')}"
                f"{mark}"
            )
    return "\n".join(lines)


def main() -> int:
    print("questions", QUESTIONS.as_posix())
    report = run_metrics()
    print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
