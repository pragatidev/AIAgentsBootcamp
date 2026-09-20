"""Upload eval/golden.jsonl to LangSmith and score it with a code evaluator.

No key: the same evaluator runs locally and prints fallback. Never invents
a dataset id or an experiment url.
"""

from __future__ import annotations

from typing import Any

from eval.runners.golden import load_golden
from eval.runners.rag_metrics import _refused, _source_blob


DATASET_NAME = "dataflow-golden"


def example_inputs(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "input": row.get("input") or row.get("question") or "",
        "kind": row.get("kind") or "",
    }


def example_outputs(row: dict[str, Any]) -> dict[str, Any] | None:
    """Reference outputs. None when the golden row has no reference to score."""
    kind = str(row.get("kind") or "")
    ref = row.get("reference")
    if ref is None:
        if kind == "refuse":
            return {"kind": "refuse", "must_refuse": True}
        return None
    if not isinstance(ref, dict):
        return {"kind": kind, "reference": ref}
    out: dict[str, Any] = {"kind": kind}
    if ref.get("source"):
        out["source"] = ref.get("source")
    if ref.get("fact"):
        out["fact"] = ref.get("fact")
    if ref.get("order_id"):
        out["order_id"] = ref.get("order_id")
    if ref.get("status"):
        out["status"] = ref.get("status")
    if ref.get("action"):
        out["action"] = ref.get("action")
    if ref.get("must_not_call"):
        out["must_not_call"] = list(ref.get("must_not_call") or [])
    if kind == "refuse" and not out.get("must_not_call"):
        out["must_refuse"] = True
    if len(out) == 1 and kind != "refuse":
        return None
    return out


def exact_source_or_refuse(run: Any, example: Any) -> dict[str, Any]:
    """Code evaluator. Skip when the example has no reference outputs."""
    outputs = getattr(example, "outputs", None)
    if not outputs:
        return {
            "key": "exact_source_or_refuse",
            "score": None,
            "comment": "skipped: missing reference",
        }
    pred = getattr(run, "outputs", None) or {}
    kind = str(outputs.get("kind") or "")
    answer = str(pred.get("answer") or pred.get("reply") or "")
    sources = _source_blob(pred.get("sources") or []) + " " + _source_blob(
        pred.get("passages") or []
    )
    blob = (answer + " " + sources).replace("\\", "/")
    if kind == "refuse" or outputs.get("must_refuse"):
        ok = _refused(answer)
        return {
            "key": "exact_source_or_refuse",
            "score": 1 if ok else 0,
            "comment": "refuse" if ok else "did not refuse",
        }
    expected = str(outputs.get("source") or "")
    if expected:
        ok = expected.replace("\\", "/") in blob
        return {
            "key": "exact_source_or_refuse",
            "score": 1 if ok else 0,
            "comment": "source hit" if ok else "source miss",
        }
    fact = str(outputs.get("fact") or "")
    if fact:
        ok = fact.lower() in blob.lower()
        return {
            "key": "exact_source_or_refuse",
            "score": 1 if ok else 0,
            "comment": "fact hit" if ok else "fact miss",
        }
    order_id = str(outputs.get("order_id") or "")
    status = str(outputs.get("status") or "")
    if order_id:
        ok = order_id in blob and (not status or status.lower() in blob.lower())
        return {
            "key": "exact_source_or_refuse",
            "score": 1 if ok else 0,
            "comment": "lookup hit" if ok else "lookup miss",
        }
    return {
        "key": "exact_source_or_refuse",
        "score": None,
        "comment": "skipped: missing reference",
    }


def ensure_dataset(client: Any, name: str = DATASET_NAME) -> Any:
    """create_dataset, or read_dataset by name if it already exists."""
    try:
        dataset = client.read_dataset(dataset_name=name)
        print("dataset_reused", getattr(dataset, "name", name), flush=True)
        print("dataset_id", getattr(dataset, "id", ""), flush=True)
        return dataset
    except Exception as exc:
        print("dataset_read_miss", type(exc).__name__, flush=True)
    dataset = client.create_dataset(
        dataset_name=name,
        description="DataFlow golden set from eval/golden.jsonl",
    )
    print("dataset_created", getattr(dataset, "name", name), flush=True)
    print("dataset_id", getattr(dataset, "id", ""), flush=True)
    return dataset


def create_row_example(
    client: Any,
    dataset_id: Any,
    row: dict[str, Any],
    *,
    include_reference: bool,
) -> Any:
    inputs = example_inputs(row)
    outputs = example_outputs(row) if include_reference else None
    example = client.create_example(
        dataset_id=dataset_id,
        inputs=inputs,
        outputs=outputs,
        metadata={"golden_id": row.get("id"), "kind": row.get("kind")},
    )
    print(
        "example",
        row.get("id"),
        "id",
        getattr(example, "id", ""),
        "has_reference",
        outputs is not None,
        flush=True,
    )
    return example


def experiment_rows(results: Any) -> list[Any]:
    rows = getattr(results, "_results", None)
    if rows is None:
        return []
    return list(rows)


def print_experiment(results: Any) -> None:
    name = getattr(results, "experiment_name", None)
    url = getattr(results, "url", None)
    print("experiment_name", name, flush=True)
    print("experiment_url", url, flush=True)
    scored = 0
    skipped = 0
    rows = experiment_rows(results)
    if not rows:
        try:
            rows = list(results)
        except Exception:
            rows = []
    for row in rows:
        if isinstance(row, dict):
            example = row.get("example")
            ev = row.get("evaluation_results")
        else:
            example = getattr(row, "example", None)
            ev = getattr(row, "evaluation_results", None)
        inputs = getattr(example, "inputs", None) or {}
        eid = inputs.get("id") or getattr(example, "id", "")
        items: list[Any] = []
        if isinstance(ev, dict) and "results" in ev:
            items = list(ev.get("results") or [])
        elif hasattr(ev, "results"):
            items = list(ev.results or [])
        elif ev is not None:
            items = [ev]
        if not items:
            print("example_score", eid, "none", flush=True)
            skipped += 1
            continue
        for item in items:
            if isinstance(item, dict):
                key = item.get("key")
                score = item.get("score")
                comment = item.get("comment")
            else:
                key = getattr(item, "key", "")
                score = getattr(item, "score", None)
                comment = getattr(item, "comment", None)
            print(
                "example_score",
                eid,
                "key",
                key,
                "score",
                score,
                "comment",
                comment,
                flush=True,
            )
            if score is None:
                skipped += 1
            else:
                scored += 1
    print("n_scored", scored, flush=True)
    print("n_skipped", skipped, flush=True)


def desk_target_factory(graph: Any, model: Any = None):
    """Target for langsmith.evaluate. One ticket in, answer and sources out."""
    from eval.runners.rag_metrics import run_agentic

    def target(inputs: dict[str, Any]) -> dict[str, Any]:
        question = str(inputs.get("input") or inputs.get("question") or "")
        print("target", inputs.get("id"), flush=True)
        result = run_agentic(question, model=model, graph=graph)
        return {
            "answer": result.get("answer") or "",
            "reply": result.get("answer") or "",
            "sources": result.get("sources") or [],
            "passages": result.get("passages") or [],
            "route": result.get("route"),
            "refused": result.get("refused"),
        }

    return target


def load_named_rows(ids: list[str]) -> list[dict[str, Any]]:
    by_id = {str(row.get("id")): row for row in load_golden()}
    out: list[dict[str, Any]] = []
    for gid in ids:
        row = by_id.get(gid)
        if row is None:
            raise KeyError("golden row missing: " + gid)
        out.append(row)
    return out
