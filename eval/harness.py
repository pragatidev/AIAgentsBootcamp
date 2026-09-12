"""Eval harness the PM and QA own.

Two judges. The plant is the same model that wrote the answer scoring
itself: every row passes, including a fluent miss. The fix is the golden
check: reference facts and must-not-call rows. Nothing in the agent
changes. The harness is the win.

Curriculum path: evals/harness.py (shim). Golden set: eval/golden.jsonl.
"""

from __future__ import annotations

from typing import Any

from dataflow.graphs.rag_graph import REFUSE_TEMPLATE
from eval.runners.golden import fixture_run, load_golden

FLUENT_MISS_ANSWER = (
    "You have a ninety-day refund window from delivery. "
    "We are happy to take the unused lamp back."
)
FLUENT_MISS_ID = "policy-return"
DEMO_IDS = (
    "policy-return",
    "lookup-1001",
    "refuse-coffee",
    "park-refund-1001",
    "refuse-injection-escalate",
)


def _content(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "\n".join(part for part in parts if part).strip()
    return str(content or "").strip()


def load_demo_rows(path=None) -> list[dict[str, Any]]:
    """Golden rows the harness table walks. Subset so the lab stays short."""
    rows = load_golden(path)
    wanted = {str(item) for item in DEMO_IDS}
    picked = [row for row in rows if str(row.get("id")) in wanted]
    by_id = {str(row.get("id")): row for row in picked}
    return [by_id[item] for item in DEMO_IDS if item in by_id]


def plant_results(
    rows: list[dict[str, Any]],
    *,
    miss_id: str = FLUENT_MISS_ID,
) -> list[dict[str, Any]]:
    """Fixture desk answers, plus one planted fluent miss. Agent unchanged."""
    out: list[dict[str, Any]] = []
    for row in rows:
        result = dict(fixture_run(row))
        if str(row.get("id")) == miss_id:
            result["answer"] = FLUENT_MISS_ANSWER
            result["passages"] = []
            result["sources"] = []
            result["refused"] = False
            result["planted_fluent_miss"] = True
        out.append(result)
    return out


def self_score(
    row: dict[str, Any],
    result: dict[str, Any],
    *,
    model: Any = None,
) -> dict[str, Any]:
    """Writer-as-judge. The same model that wrote the answer scores itself.

    Every row passes. That is the plant. An optional model call is shown
    on the row as model_said and does not change the verdict.
    """
    answer = str(result.get("answer") or "")
    model_said = ""
    if model is not None:
        prompt = (
            "You wrote this support answer. Score your own writing. "
            "Reply PASS or FAIL.\n\n"
            + answer
        )
        model_said = _content(model.invoke(prompt))
    return {
        "id": row.get("id"),
        "kind": row.get("kind"),
        "verdict": "PASS",
        "reason": "self-judge",
        "answer": answer,
        "model_said": model_said,
        "planted_fluent_miss": bool(result.get("planted_fluent_miss")),
    }


def golden_check(
    row: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Reference facts and must-not-call. No model. The agent is not edited."""
    kind = str(row.get("kind") or "")
    ref = row.get("reference") or {}
    answer = str(result.get("answer") or "")
    blob = answer.lower()
    reason = "ok"
    ok = False

    if kind == "refuse" and isinstance(ref, dict) and ref.get("must_not_call"):
        banned = [str(item) for item in ref.get("must_not_call") or []]
        called = [str(item) for item in (result.get("tools_called") or [])]
        hit = [name for name in banned if name in called]
        ok = not hit
        reason = "must-not-call clean" if ok else "called " + ",".join(hit)
    elif kind == "refuse":
        ok = "i do not have that in the knowledge base" in blob
        reason = "refuse template" if ok else "missing refuse template"
    elif kind == "park":
        expected = ref.get("action") if isinstance(ref, dict) else None
        parked = bool(result.get("parked"))
        action = result.get("interrupt_action")
        ok = parked and (expected is None or action == expected)
        reason = "parked" if ok else "not parked"
    elif kind == "lookup":
        oid = str(ref.get("order_id") or "") if isinstance(ref, dict) else ""
        status = str(ref.get("status") or "") if isinstance(ref, dict) else ""
        ok = bool(oid) and oid.lower() in blob and status.lower() in blob
        reason = "order and status" if ok else "missing order fact"
    else:
        fact = str(ref.get("fact") or "") if isinstance(ref, dict) else ""
        ok = bool(fact) and fact.lower() in blob
        reason = "has fact" if ok else "missing fact " + fact

    return {
        "id": row.get("id"),
        "kind": kind,
        "verdict": "PASS" if ok else "FAIL",
        "reason": reason,
        "answer": answer,
        "model_said": "",
        "planted_fluent_miss": bool(result.get("planted_fluent_miss")),
    }


def run_harness(
    rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    mode: str = "golden",
    model: Any = None,
) -> list[dict[str, Any]]:
    """Score each (row, result). mode is self or golden."""
    scored: list[dict[str, Any]] = []
    for row, result in zip(rows, results):
        if mode == "self":
            scored.append(self_score(row, result, model=model))
        else:
            scored.append(golden_check(row, result))
    return scored


def render_table(scored: list[dict[str, Any]]) -> str:
    lines = ["id kind verdict reason"]
    for row in scored:
        lines.append(
            str(row.get("id") or "")
            + " "
            + str(row.get("kind") or "")
            + " "
            + str(row.get("verdict") or "")
            + " "
            + str(row.get("reason") or "")
        )
    return "\n".join(lines)


def refuse_template_for(question: str) -> str:
    return REFUSE_TEMPLATE.format(q=question)


def main() -> int:
    rows = load_demo_rows()
    results = plant_results(rows)
    print("golden", "eval/golden.jsonl")
    print("rows", len(rows))
    print("self-judge")
    print(render_table(run_harness(rows, results, mode="self")))
    print("golden-check")
    print(render_table(run_harness(rows, results, mode="golden")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
