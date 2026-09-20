"""LLM as judge for DataFlow answers, with and without must-cite-a-file.

Uses config.get_chat_model(). A fixture model can be passed so pytest
stays off Ollama. Never invents a score.
"""

from __future__ import annotations

import re
from typing import Any

from config import get_chat_model
from dataflow.graphs.rag_graph import REFUSE_TEMPLATE
from eval.judges.llm_judge import canonical_sample, load_labels
from eval.runners.golden import load_golden

HELPFUL_RUBRIC = (
    "You judge only fluency and helpful tone. Ignore whether the facts "
    "are true. Ignore whether a file is cited. If the answer is a complete "
    "polite paragraph a customer could read, score 1. Empty or garbled "
    "scores 0. Reply with 0 or 1 only."
)

MUST_CITE_RUBRIC = (
    "You judge a DataFlow support answer. "
    "A correct refusal (the knowledge base does not have it) scores 1 "
    "even with no file. "
    "If the answer makes a policy claim, it must cite a source file "
    "(a path such as return_policy.md or a Sources block). "
    "A fluent policy answer with no file is 0. "
    "A ninety-day or 90 day refund claim with no file name is 0. "
    "Reply with 0 or 1 only."
)

FLUENT_WRONG_PLANT = (
    "You have a ninety-day refund window from delivery. "
    "We are happy to take the unused lamp back."
)
FLUENT_WRONG_ANSWER = FLUENT_WRONG_PLANT
FLUENT_WRONG_ANSWER = FLUENT_WRONG_PLANT


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


def parse_score(text: str) -> int:
    raw = (text or "").strip()
    for char in raw:
        if char == "1":
            return 1
        if char == "0":
            return 0
    lower = raw.lower()
    if re.search(r"\bpass\b", lower) or re.search(r"\byes\b", lower):
        return 1
    return 0


def judge_answer(
    answer: str,
    passages: list[Any] | None = None,
    *,
    must_cite_file: bool = False,
    model: Any = None,
) -> dict[str, Any]:
    chat = model or get_chat_model()
    rubric = MUST_CITE_RUBRIC if must_cite_file else HELPFUL_RUBRIC
    blob_parts: list[str] = []
    if must_cite_file:
        for row in passages or []:
            if isinstance(row, dict):
                blob_parts.append(
                    f"Source: {row.get('source')}\n{row.get('text')}"
                )
            else:
                blob_parts.append(str(row))
    blob = "\n\n".join(blob_parts) if blob_parts else "(none)"
    result = chat.invoke(
        [
            {"role": "system", "content": rubric},
            {
                "role": "user",
                "content": f"Passages:\n{blob}\n\nAnswer:\n{answer}",
            },
        ]
    )
    raw = _content(result)
    score = parse_score(raw)
    return {
        "score": score,
        "raw": raw,
        "must_cite_file": must_cite_file,
        "answer": answer,
    }


def three_samples(
    *,
    grounded_answer: str | None = None,
    grounded_passages: list[Any] | None = None,
    refuse_answer: str | None = None,
) -> list[dict[str, Any]]:
    """Grounded, fluent-wrong, refuse. Desk runs if given, else golden rows."""
    golden = {str(row.get("id")): row for row in load_golden()}
    labels = {str(row.get("id")): row for row in load_labels()}
    grounded_row = golden.get("policy-return") or {}
    refuse_row = golden.get("refuse-coffee") or {}
    grounded_sample = canonical_sample(grounded_row)
    refuse_sample = canonical_sample(refuse_row)
    grounded = {
        "id": "grounded",
        "kind": "grounded",
        "question": grounded_row.get("input") or "",
        "answer": grounded_answer or grounded_sample.get("answer") or "",
        "passages": grounded_passages
        if grounded_passages is not None
        else list(grounded_sample.get("passages") or []),
        "human": (labels.get("policy-return") or {}).get("label") or "grounded",
    }
    fluent = {
        "id": "fluent_wrong",
        "kind": "fluent_wrong",
        "question": grounded_row.get("input") or "",
        "answer": FLUENT_WRONG_PLANT,
        "passages": [
            {
                "source": "dataflow/wiki/return_policy.md",
                "text": (
                    "The customer return window is 30 days from delivery. "
                    "Returns are allowed within 30 days of delivery when "
                    "the item is unused."
                ),
            }
        ],
        "human": "fluent_wrong",
    }
    refuse = {
        "id": "refuse",
        "kind": "refuse",
        "question": refuse_row.get("input") or "",
        "answer": refuse_answer
        or refuse_sample.get("answer")
        or REFUSE_TEMPLATE.format(q=refuse_row.get("input") or ""),
        "passages": [],
        "human": (labels.get("refuse-coffee") or {}).get("label") or "refuse",
    }
    return [grounded, fluent, refuse]


def score_three(
    samples: list[dict[str, Any]],
    *,
    must_cite_file: bool,
    model: Any = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sample in samples:
        judged = judge_answer(
            str(sample.get("answer") or ""),
            list(sample.get("passages") or []),
            must_cite_file=must_cite_file,
            model=model,
        )
        row = dict(sample)
        row["score"] = judged["score"]
        row["raw"] = judged["raw"]
        row["must_cite_file"] = must_cite_file
        out.append(row)
    return out


def langsmith_evaluator(must_cite_file: bool = True, model: Any = None):
    """Evaluator signature for langsmith.evaluate: (run, example) -> dict."""

    def _eval(run: Any, example: Any) -> dict[str, Any]:
        pred = getattr(run, "outputs", None) or {}
        answer = str(pred.get("answer") or pred.get("reply") or "")
        passages = list(pred.get("passages") or [])
        judged = judge_answer(
            answer,
            passages,
            must_cite_file=must_cite_file,
            model=model,
        )
        return {
            "key": "llm_judge",
            "score": judged["score"],
            "comment": judged["raw"][:240],
        }

    return _eval
