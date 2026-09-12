# %%
"""S10.4 Trim keeps the last N. No model."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.graphs.trim import trim_messages

# %%
messages = [
    "ticket DF-1001",
    "looked up desk lamp",
    "policy 30 days",
    "human asked again",
    "ticket DF-1002",
    "looked up mug",
]
print("before", len(messages))
print("after", trim_messages(messages, keep=4))
print("keep", 4)
