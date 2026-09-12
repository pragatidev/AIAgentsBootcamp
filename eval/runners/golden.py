"""Load the DataFlow golden set, score the agentic desk, write baseline.md."""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import ROOT, get_chat_model, get_embeddings
from dataflow.graphs.rag_graph import REFUSE_TEMPLATE, build_rag_graph
from dataflow.rag.chunk import chunk_by_heading, chunk_recursive
from dataflow.rag.load import load_knowledge_base
from dataflow.tools.retrieve import reset_index, set_index
from eval.runners.rag_metrics import run_agentic, score_row

GOLDEN = ROOT / "eval" / "golden.jsonl"
BASELINE = ROOT / "eval" / "baseline.md"
LAST_RUN = ROOT / "eval" / "last_run.md"

PUNCT = re.compile(r"[^a-z0-9]+")
KINDS = ("policy", "lookup", "refuse", "park")
OVERALL_METRICS = (
    "faithfulness",
    "context_recall",
    "refused_correctly",
    "fluent_misses",
    "latency_s",
)


def load_golden(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or GOLDEN
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def normalize_input(text: str) -> str:
    return PUNCT.sub("", (text or "").lower())


def unique_tickets(rows: list[dict[str, Any]]) -> int:
    seen: set[str] = set()
    for row in rows:
        text = str(row.get("input") or row.get("question") or "")
        seen.add(normalize_input(text))
    return len(seen)


def git_commit() -> str:
    try:
        raw = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
        )
        return raw.decode("utf-8").strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _as_score_input(row: dict[str, Any]) -> dict[str, Any]:
    ref = row.get("reference") or {}
    source = ""
    if isinstance(ref, dict):
        source = str(ref.get("source") or "")
    kind = str(row.get("kind") or "")
    mapped = kind
    if kind == "park":
        mapped = "policy"
    return {
        "id": row.get("id"),
        "kind": mapped if mapped in {"policy", "lookup", "refuse"} else "policy",
        "question": row.get("input") or row.get("question") or "",
        "expected_source": source,
    }


def run_park(
    row: dict[str, Any],
    *,
    model: Any = None,
) -> dict[str, Any]:
    from langgraph.checkpoint.memory import InMemorySaver

    from dataflow.graphs.v4_hitl import build_v4_hitl

    saver = InMemorySaver()
    graph = build_v4_hitl(model=model, checkpointer=saver)
    thread = "golden-" + str(row.get("id") or "park")
    cfg = {"configurable": {"thread_id": thread}}
    started = time.perf_counter()
    graph.invoke({"ticket": str(row.get("input") or "")}, cfg)
    latency = time.perf_counter() - started
    state = graph.get_state(cfg)
    action = None
    if state.interrupts:
        payload = state.interrupts[0].value
        if isinstance(payload, dict):
            action = payload.get("action")
    values = state.values or {}
    return {
        "answer": str(values.get("reply") or ""),
        "sources": [],
        "passages": [],
        "refused": False,
        "route": str(values.get("route") or "park"),
        "interrupt_action": action,
        "parked": bool(state.interrupts),
        "latency": latency,
        "state": values,
    }


def _passages_blob(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in list(result.get("passages") or []) + list(result.get("sources") or []):
        if isinstance(item, dict):
            parts.append(str(item.get("text") or ""))
        else:
            parts.append(str(item))
    return " ".join(parts).lower()


def score_golden_row(
    row: dict[str, Any],
    result: dict[str, Any],
    *,
    judge: Callable[..., int] | None = None,
    model: Any = None,
) -> dict[str, Any]:
    kind = str(row.get("kind") or "")
    if kind == "park":
        ref = row.get("reference") or {}
        expected = ref.get("action") if isinstance(ref, dict) else None
        parked_ok = bool(result.get("parked")) and (
            expected is None or result.get("interrupt_action") == expected
        )
        return {
            "id": row.get("id"),
            "kind": "park",
            "faithfulness": 1 if parked_ok else 0,
            "context_recall": 1 if parked_ok else 0,
            "refused_correctly": 0,
            "fluent_miss": not parked_ok,
            "answer": result.get("answer") or "",
            "route": result.get("route"),
            "latency": float(result.get("latency") or 0.0),
        }
    scored = score_row(_as_score_input(row), result, judge=judge, model=model)
    scored["kind"] = kind
    scored["latency"] = float(result.get("latency") or 0.0)
    ref = row.get("reference") or {}
    fact = str(ref.get("fact") or "") if isinstance(ref, dict) else ""
    if kind == "policy" and fact:
        # A source file hit is not enough if the cut lost the named fact.
        if fact.lower() not in _passages_blob(result):
            scored["context_recall"] = 0
    return scored


def fixture_run(row: dict[str, Any]) -> dict[str, Any]:
    """Scripted desk for CI. No Ollama. Lives behind --fixture only."""
    kind = str(row.get("kind") or "")
    inp = str(row.get("input") or "")
    ref = row.get("reference") or {}
    if kind == "refuse":
        text = REFUSE_TEMPLATE.format(q=inp)
        return {
            "answer": text,
            "sources": [],
            "passages": [],
            "refused": True,
            "route": "retrieve",
            "latency": 0.0,
        }
    if kind == "lookup":
        oid = ref.get("order_id") if isinstance(ref, dict) else ""
        status = ref.get("status") if isinstance(ref, dict) else ""
        text = f"Order {oid} is {status}."
        return {
            "answer": text,
            "sources": [],
            "passages": [],
            "refused": False,
            "route": "lookup",
            "latency": 0.0,
        }
    if kind == "park":
        action = ref.get("action") if isinstance(ref, dict) else "refund"
        return {
            "answer": "",
            "sources": [],
            "passages": [],
            "refused": False,
            "route": "refund",
            "interrupt_action": action,
            "parked": True,
            "latency": 0.0,
        }
    source = ref.get("source") if isinstance(ref, dict) else ""
    fact = ref.get("fact") if isinstance(ref, dict) else ""
    text = f"{fact}"
    passage = {"source": source, "text": str(fact)}
    return {
        "answer": text,
        "sources": [passage],
        "passages": [passage],
        "refused": False,
        "route": "retrieve",
        "latency": 0.0,
    }


def _embed_index(chunks: list, embeddings: Any, batch: int = 16):
    """Embed in small batches. A single from_documents call can trip Ollama."""
    from langchain_community.vectorstores import FAISS

    index = None
    i = 0
    while i < len(chunks):
        piece = chunks[i : i + batch]
        texts = [chunk.page_content for chunk in piece]
        metas = [chunk.metadata for chunk in piece]
        try:
            vecs = embeddings.embed_documents(texts)
        except Exception:
            vecs = embeddings.embed_documents(texts)
        pairs = list(zip(texts, vecs))
        if index is None:
            index = FAISS.from_embeddings(pairs, embeddings, metadatas=metas)
        else:
            index.add_embeddings(pairs, metadatas=metas)
        i += batch
    if index is None:
        raise ValueError("no chunks to index")
    return index


def _build_index(chunker: str, chunk_size: int | None, embeddings: Any = None):
    from dataflow.rag.faiss_index import load_faiss_index

    docs = load_knowledge_base()
    if chunker == "recursive":
        size = int(chunk_size or 300)
        chunks = chunk_recursive(docs, chunk_size=size, chunk_overlap=0)
        cache = ROOT / "dataflow" / "data" / f"faiss_index_rec{size}"
    else:
        chunks = chunk_by_heading(docs)
        cache = None
    embeddings = embeddings or get_embeddings()
    if cache is not None and (cache / "index.faiss").is_file():
        return load_faiss_index(cache, embeddings=embeddings)
    index = _embed_index(chunks, embeddings)
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        index.save_local(str(cache))
    return index


def summarize_golden(scores: list[dict[str, Any]]) -> dict[str, Any]:
    overall: dict[str, Any] = {
        "faithfulness": _mean([float(s["faithfulness"]) for s in scores]),
        "context_recall": _mean([float(s["context_recall"]) for s in scores]),
        "refused_correctly": _mean(
            [
                float(s["refused_correctly"])
                for s in scores
                if s.get("kind") == "refuse"
            ]
        ),
        "fluent_misses": sum(1 for s in scores if s.get("fluent_miss")),
        "latency_s": _mean([float(s.get("latency") or 0.0) for s in scores]),
    }
    by_kind: dict[str, Any] = {}
    for kind in KINDS:
        rows = [s for s in scores if s.get("kind") == kind]
        by_kind[kind] = {
            "faithfulness": _mean([float(s["faithfulness"]) for s in rows]),
            "context_recall": _mean([float(s["context_recall"]) for s in rows]),
            "refused_correctly": _mean(
                [float(s["refused_correctly"]) for s in rows]
            ),
            "fluent_misses": sum(1 for s in rows if s.get("fluent_miss")),
            "latency_s": _mean([float(s.get("latency") or 0.0) for s in rows]),
            "n": len(rows),
        }
    return {"all": overall, "by_kind": by_kind}


def render_baseline(
    unique: int,
    scores: list[dict[str, Any]],
    *,
    commit: str | None = None,
    when: str | None = None,
) -> str:
    summary = summarize_golden(scores)
    when = when or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    commit = commit or git_commit()
    lines = [
        f"unique_tickets: {unique}",
        f"date: {when}",
        f"commit: {commit}",
        "",
        "overall",
        f"faithfulness {summary['all']['faithfulness']:.3f}",
        f"context_recall {summary['all']['context_recall']:.3f}",
        f"refused_correctly {summary['all']['refused_correctly']:.3f}",
        f"fluent_misses {summary['all']['fluent_misses']}",
        f"latency_s {summary['all']['latency_s']:.2f}",
        "",
        "per_kind",
    ]
    for kind in KINDS:
        row = summary["by_kind"][kind]
        lines.append(
            f"{kind} faithfulness {row['faithfulness']:.3f} "
            f"n={row['n']}"
        )
        lines.append(f"{kind} context_recall {row['context_recall']:.3f}")
        lines.append(f"{kind} refused_correctly {row['refused_correctly']:.3f}")
        lines.append(f"{kind} fluent_misses {row['fluent_misses']}")
    lines.append("")
    lines.append("per_row")
    for scored in scores:
        mark = " FLUENT_MISS" if scored.get("fluent_miss") else ""
        lines.append(
            f"{scored.get('id')} kind={scored.get('kind')} "
            f"faith={scored.get('faithfulness')} "
            f"recall={scored.get('context_recall')} "
            f"refuse={scored.get('refused_correctly')} "
            f"route={scored.get('route')}"
            f"{mark}"
        )
    return "\n".join(lines) + "\n"


def parse_metrics_file(path: Path) -> dict[str, float]:
    """Read overall metric lines (the two-token rows) from a baseline file."""
    metrics: dict[str, float] = {}
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("unique_tickets:"):
            continue
        parts = stripped.split()
        if len(parts) == 2 and parts[0] in OVERALL_METRICS:
            metrics[parts[0]] = float(parts[1])
    return metrics


def parse_unique_tickets(path: Path) -> int:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("unique_tickets:"):
            return int(line.split(":", 1)[1].strip())
    return 0


def write_metrics_file(
    path: Path,
    unique: int,
    scores: list[dict[str, Any]],
    *,
    commit: str | None = None,
    when: str | None = None,
) -> str:
    text = render_baseline(unique, scores, commit=commit, when=when)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def fixture_judge(answer: str, passages: list, model=None) -> int:
    return 1


def run_golden(
    path: Path | None = None,
    *,
    model: Any = None,
    fixture: bool = False,
    chunker: str = "heading",
    chunk_size: int | None = None,
    retrieve_k: int | None = None,
    judge: Callable[..., int] | None = None,
    progress: bool = True,
) -> dict[str, Any]:
    rows = load_golden(path)
    swapped = False
    try:
        if fixture:
            judge = judge or fixture_judge

            def run_one(row: dict[str, Any]) -> dict[str, Any]:
                return fixture_run(row)

        else:
            chat = model or get_chat_model()
            if chunker == "recursive" or chunk_size:
                index = _build_index(chunker, chunk_size)
                set_index(index)
                swapped = True
            # Character cut at 300 loses headings. k=1 so a lost name
            # cannot hide in the other two passages.
            if retrieve_k is None:
                retrieve_k = 1 if chunker == "recursive" else 3
            graph = build_rag_graph(
                model=chat, scope="all", retrieve_k=int(retrieve_k)
            )

            def run_one(row: dict[str, Any], _chat=chat, _graph=graph) -> dict[str, Any]:
                if str(row.get("kind") or "") == "park":
                    return run_park(row, model=_chat)
                return run_agentic(
                    str(row.get("input") or ""),
                    model=_chat,
                    graph=_graph,
                )

        scores: list[dict[str, Any]] = []
        for row in rows:
            if progress:
                print("row", row.get("id"), "kind", row.get("kind"), flush=True)
            result = run_one(row)
            scored = score_golden_row(row, result, judge=judge, model=model)
            scores.append(scored)
            if progress:
                print(
                    "scored",
                    scored.get("id"),
                    "faith",
                    scored.get("faithfulness"),
                    "recall",
                    scored.get("context_recall"),
                    "refuse",
                    scored.get("refused_correctly"),
                    flush=True,
                )
        unique = unique_tickets(rows)
        return {
            "rows": rows,
            "scores": scores,
            "unique_tickets": unique,
            "summary": summarize_golden(scores),
        }
    finally:
        if swapped:
            reset_index()


def write_baseline(
    dest: Path | None = None,
    *,
    report: dict[str, Any] | None = None,
    **run_kwargs: Any,
) -> Path:
    dest = dest or BASELINE
    report = report or run_golden(**run_kwargs)
    write_metrics_file(
        dest,
        int(report["unique_tickets"]),
        list(report["scores"]),
    )
    return dest


def main() -> int:
    print("golden", GOLDEN.as_posix(), flush=True)
    dest = write_baseline()
    print("wrote", dest.as_posix(), flush=True)
    print(dest.read_text(encoding="utf-8"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
