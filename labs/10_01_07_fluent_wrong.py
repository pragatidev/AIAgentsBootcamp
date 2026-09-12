# %% [markdown]
# Fail a fluent-wrong DataFlow answer.
#
# When this works, a planted ninety-day refund paragraph passes the
# helpful heuristic and fails claim versus chunk, with the unsupported
# claim named. Lookup rows are tagged and skipped.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from eval.runners.faithfulness import (
    claims_of,
    helpful_heuristic,
    is_lookup_row,
    score_answer,
    supported_by_chunks,
)

print("model", config.CHAT_MODEL)
plant = (
    "You have a ninety-day refund window from delivery. "
    "We are happy to take the unused lamp back."
)
chunks = [
    {
        "source": "dataflow/wiki/return_policy.md",
        "text": (
            "The customer return window is 30 days from delivery. "
            "Returns are allowed within 30 days of delivery when the item is unused."
        ),
    }
]
print("plant")
print(plant)
print("chunk_source", chunks[0]["source"])
print("chunk")
print(chunks[0]["text"])

# %%
print("cell", "heuristic")
# Planted scorer. Passes any fluent answer. This is the lab
# misbehaving on purpose: helpful is not grounded.
heuristic_pass = helpful_heuristic(plant)
print("helpful_heuristic", heuristic_pass)

# %%
print("cell", "claims_versus_chunks")
claims = claims_of(plant)
print("claims", claims)
unsupported: list[str] = []
for claim in claims:
    ok = supported_by_chunks(claim, chunks)
    print("claim", claim)
    print("supported_by_chunks", ok)
    if not ok:
        unsupported.append(claim)
print("unsupported_claims", unsupported)
print("claim_check_fail", bool(unsupported))
print("heuristic_verdict", "PASS" if heuristic_pass else "FAIL")
print("claim_verdict", "FAIL" if unsupported else "PASS")

# %%
print("cell", "lookup_skipped")
lookup_row = {
    "id": "lookup-1001",
    "kind": "lookup",
    "tags": ["lookup"],
}
print("is_lookup_row", is_lookup_row(lookup_row))
skipped = score_answer(
    lookup_row,
    "Order DF-1001 is delivered.",
    [],
)
print("lookup_skipped", skipped.get("skipped"), skipped.get("reason"))
