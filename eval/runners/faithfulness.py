"""Claim versus chunk faithfulness for the DataFlow desk.

Faithfulness is not helpfulness. Split the answer into claims, then
ask whether each claim appears in the retrieved chunks. Lookup rows
are tagged and skipped: a passage judge has nothing to check.
"""

from __future__ import annotations

import re
from typing import Any

from config import get_chat_model

CLAIM_SPLIT = re.compile(r"(?<=[.!?])\s+")

SUPPORT_SYSTEM = (
    "You decide whether a retrieved passage supports one claim. "
    "The passage is the only evidence. If the claim is stated or "
    "clearly implied by the passage, reply YES. If the claim adds a "
    "number, policy, or fact that is not in the passage, reply NO. "
    "Reply YES or NO only."
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


def claims_of(answer: str) -> list[str]:
    """Split an answer into claims, one sentence or one fact each."""
    text = (answer or "").strip()
    if not text:
        return []
    parts = CLAIM_SPLIT.split(text)
    claims: list[str] = []
    for part in parts:
        item = part.strip()
        if not item:
            continue
        claims.append(item)
    return claims


def supported_by_chunks(
    claim: str,
    chunks: list[Any],
    model: Any = None,
) -> bool:
    """Ask the model the narrow question with the chunk text in front.

    A tests fixture path exists: pass model=FakeChatModel(reply='yes')
    or reply='no' and this function does not call Ollama.
    """
    blob_parts: list[str] = []
    for chunk in chunks or []:
        if isinstance(chunk, str):
            blob_parts.append(chunk)
        elif isinstance(chunk, dict):
            blob_parts.append(str(chunk.get("text") or ""))
        else:
            blob_parts.append(str(getattr(chunk, "page_content", chunk)))
    blob = "\n\n".join(part for part in blob_parts if part).strip()
    chat = model or get_chat_model()
    result = chat.invoke(
        [
            {"role": "system", "content": SUPPORT_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Passage:\n{blob or '(none)'}\n\n"
                    f"Claim:\n{claim}\n\n"
                    "Does the passage support the claim? Reply YES or NO only."
                ),
            },
        ]
    )
    text = _content(result).strip().lower()
    if re.search(r"\bno\b", text) and not text.startswith("yes"):
        return False
    if re.search(r"\byes\b", text):
        return True
    if text.startswith("no"):
        return False
    return False


def helpful_heuristic(answer: str) -> bool:
    """Planted scorer. Passes any fluent answer. Not a real metric.

    This is the lab misbehaving on purpose: a warm complete paragraph
    scores as a pass even when every fact is invented.
    """
    text = (answer or "").strip()
    if len(text) < 12:
        return False
    if not any(mark in text for mark in ".!?"):
        return False
    lower = text.lower()
    if "i do not have that in the knowledge base" in lower:
        return False
    return True


def is_lookup_row(row: dict[str, Any]) -> bool:
    kind = str(row.get("kind") or "")
    tags = row.get("tags") or []
    if kind == "lookup":
        return True
    if isinstance(tags, list) and "lookup" in tags:
        return True
    return False


def score_answer(
    row: dict[str, Any],
    answer: str,
    chunks: list[Any],
    *,
    model: Any = None,
) -> dict[str, Any]:
    """Faithfulness for one golden row. Lookup rows are skipped."""
    if is_lookup_row(row):
        return {
            "id": row.get("id"),
            "skipped": True,
            "reason": "lookup",
            "faithful": None,
            "unsupported": [],
        }
    claims = claims_of(answer)
    unsupported: list[str] = []
    for claim in claims:
        if not supported_by_chunks(claim, chunks, model=model):
            unsupported.append(claim)
    return {
        "id": row.get("id"),
        "skipped": False,
        "faithful": not unsupported,
        "claims": claims,
        "unsupported": unsupported,
    }
