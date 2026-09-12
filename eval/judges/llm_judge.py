"""LLM as judge on the same ten golden ids a human labelled.

The judge never writes the labels file. A tests fixture path exists:
pass model=FakeChatModel(reply='grounded') and parse_verdict reads it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from config import ROOT, get_chat_model
from dataflow.graphs.rag_graph import REFUSE_TEMPLATE
from eval.runners.golden import load_golden

LABELS = ROOT / "eval" / "judges" / "human_labels.jsonl"
NOTE = ROOT / "eval" / "judges" / "calibration_note.md"

RUBRIC = (
    "You judge a DataFlow support answer. Pick exactly one label. "
    "grounded: every claim appears in the passages, or the answer is a "
    "correct order lookup with no passages needed. "
    "ungrounded: the answer adds a policy, number, or fact that is not "
    "in the passages. "
    "refuse: the answer correctly says the knowledge base does not have it. "
    "park: the desk parked a write for a person. "
    "Reply with one word: grounded, ungrounded, refuse, or park."
)

ALLOWED = ("grounded", "ungrounded", "refuse", "park")


def load_labels(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or LABELS
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def parse_verdict(text: str) -> str:
    """Parse a fixture or model verdict into one allowed label."""
    raw = (text or "").strip().lower()
    if not raw:
        return "ungrounded"
    for label in ALLOWED:
        if re.search(rf"\b{re.escape(label)}\b", raw):
            return label
    if raw.startswith("yes") or "1" in raw[:4]:
        return "grounded"
    if raw.startswith("no") or "0" in raw[:4]:
        return "ungrounded"
    return "ungrounded"


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


def canonical_sample(golden_row: dict[str, Any]) -> dict[str, Any]:
    """The artefact the human labelled: expected behaviour, not a live run."""
    kind = str(golden_row.get("kind") or "")
    ref = golden_row.get("reference") or {}
    inp = str(golden_row.get("input") or "")
    if kind == "refuse":
        return {
            "answer": REFUSE_TEMPLATE.format(q=inp),
            "passages": [],
        }
    if kind == "lookup":
        oid = ref.get("order_id") if isinstance(ref, dict) else ""
        status = ref.get("status") if isinstance(ref, dict) else ""
        return {
            "answer": f"Order {oid} is {status}.",
            "passages": [],
        }
    if kind == "park":
        action = ref.get("action") if isinstance(ref, dict) else "refund"
        return {
            "answer": f"Parked. interrupt action={action}.",
            "passages": [],
        }
    fact = ref.get("fact") if isinstance(ref, dict) else ""
    source = ref.get("source") if isinstance(ref, dict) else ""
    return {
        "answer": str(fact),
        "passages": [{"source": source, "text": str(fact)}],
    }


def judge_sample(
    sample: dict[str, Any],
    *,
    model: Any = None,
) -> str:
    chat = model or get_chat_model()
    passages = sample.get("passages") or []
    blob_parts: list[str] = []
    for row in passages:
        if isinstance(row, dict):
            blob_parts.append(
                f"Source: {row.get('source')}\n{row.get('text')}"
            )
        else:
            blob_parts.append(str(row))
    blob = "\n\n".join(blob_parts) if blob_parts else "(none)"
    result = chat.invoke(
        [
            {"role": "system", "content": RUBRIC},
            {
                "role": "user",
                "content": (
                    f"Passages:\n{blob}\n\nAnswer:\n{sample.get('answer')}"
                ),
            },
        ]
    )
    return parse_verdict(_content(result))


def judge_labelled(
    *,
    model: Any = None,
    labels_path: Path | None = None,
) -> list[dict[str, Any]]:
    golden = {str(row.get("id")): row for row in load_golden()}
    out: list[dict[str, Any]] = []
    for human in load_labels(labels_path):
        gid = str(human.get("id"))
        row = golden.get(gid) or {"id": gid, "kind": "", "input": "", "reference": None}
        sample = canonical_sample(row)
        judge_label = judge_sample(sample, model=model)
        human_label = str(human.get("label") or "")
        out.append(
            {
                "id": gid,
                "kind": row.get("kind"),
                "human": human_label,
                "judge": judge_label,
                "agree": human_label == judge_label,
                "reason": human.get("reason"),
                "answer": sample.get("answer"),
            }
        )
    return out


def trust_rule(kind: str, rows: list[dict[str, Any]]) -> str:
    subset = [row for row in rows if str(row.get("kind")) == kind]
    if not subset:
        return "never (no labelled rows of this kind)"
    agreed = sum(1 for row in subset if row.get("agree"))
    n = len(subset)
    if agreed == n:
        return "trust alone"
    if agreed == 0:
        return "never"
    return "flag for a human"


def render_note(rows: list[dict[str, Any]]) -> str:
    agreed = sum(1 for row in rows if row.get("agree"))
    n = len(rows)
    lines = [
        "# Calibration note",
        "",
        "Human labels vs the judge on the same ten golden ids.",
        "The judge did not write the labels file.",
        "",
        f"agreement: {agreed}/{n}",
        "",
        "| id | human label | judge label | agree |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['human']} | {row['judge']} | "
            f"{'yes' if row['agree'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## trust",
            "",
        ]
    )
    for kind in ("policy", "lookup", "refuse", "park"):
        lines.append(f"- {kind}: {trust_rule(kind, rows)}")
    lines.append("")
    if agreed >= (n * 2 // 3):
        lines.append(
            "They mostly agree. Keep the note anyway: the disagreements "
            "are the licence, not the matching rows."
        )
        lines.append(
            "Trust the judge alone on policy and refuse; flag lookup and "
            "park for a human; never let it decide those kinds in CI."
        )
    else:
        lines.append(
            "They disagree enough that the judge is a flag, not a gate, "
            "until more labels exist."
        )
        lines.append(
            "Do not put this judge in CI until the trust column is trust "
            "alone on the kinds you gate."
        )
    lines.append("")
    return "\n".join(lines)


def write_note(
    dest: Path | None = None,
    *,
    rows: list[dict[str, Any]] | None = None,
    model: Any = None,
) -> Path:
    dest = dest or NOTE
    rows = rows if rows is not None else judge_labelled(model=model)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_note(rows), encoding="utf-8")
    return dest
