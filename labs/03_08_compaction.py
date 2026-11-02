# %%
"""Lab 5.8: add a compaction step to the agent.

What we build: you type compact, the step that folds a long conversation. Once the conversation
passes a size you set, the older turns are folded into one summary written in a fixed shape, and
the last few messages stay word for word. Then the desk runs eighteen turns plus a question that
needs what the fold kept, and you watch the size go up, drop, go up, drop.

What you learn: the three knobs, threshold, messages kept and summary shape, as three things you
set and see. And the warning, on your screen: the summary is written by a model, and it keeps only
what its prompt asks for.

What will be true on your screen: the three knobs, one line per turn with both counts, one line
per fold with its size before and after, the number of folds, the last summary, and the desk's
answer to "Which order is this about, and how should you contact me?".
Run python -m pytest tests/test_lab_03_08.py -q to test your compact.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import (
    SUMMARIZE_PROMPT,
    ContextAgent,
    applied_window,
    chat_caller,
    count_tokens,
    summarise_with_usage,
)
from dataflow.context.rot import FILLERS

# The three knobs. Run once at 180, then at a higher threshold of your choice.
THRESHOLD = 180
KEEP_LAST = 4
# BREAK: set SUMMARY_PROMPT = "Summarize the older turns in one short sentence." and run. Read
# the summary and the last answer. Then put SUMMARIZE_PROMPT back.
SUMMARY_PROMPT = SUMMARIZE_PROMPT


# %%
# TYPE THIS: compact. Its finished copy is compact_messages in dataflow/context/agent.py.
def compact(messages: list, *, threshold: int, keep_last: int, summariser) -> tuple[list, bool, int, int]:
    """Fold the older messages into one summary once the list passes the threshold."""
    before = count_tokens(messages)
    if before <= threshold:
        return messages, False, before, before
    keep = messages[-keep_last:] if keep_last else []
    older = messages[:-keep_last] if keep_last else list(messages)
    system = [m for m in older if m.get("role") == "system"][:1]
    body = [m for m in older if m.get("role") != "system"]
    blob = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in body)
    summary = summariser(blob)
    new = system + [{"role": "assistant", "content": "SUMMARY\n" + str(summary)}] + keep
    return new, True, before, count_tokens(new)


# %%
SYSTEM = "You are the DataFlow support desk. Answer in one short sentence. Keep order ids."
PROBE = "Which order is this about, and how should you contact me?"
turns = [
    "This is about order DF-1001, the desk lamp.",
    "Please remember I want email, never a phone call.",
] + FILLERS[:16] + [PROBE]

print("threshold", THRESHOLD)
print("keep_last_messages", KEEP_LAST)
print("summary_prompt", SUMMARY_PROMPT)
agent = ContextAgent(
    chat_caller(),
    system=SYSTEM,
    compact=True,
    compact_threshold=THRESHOLD,
    keep_last=KEEP_LAST,
    compactor=compact,
    summariser=lambda text: summarise_with_usage(text, SUMMARY_PROMPT),
)
out = agent.run_turns(turns)
print("window_applied", applied_window())

# %%
print("sawtooth")
for row in out["token_trace"]:
    if row.get("event") == "compact":
        print("compact before", row["tokens_before"], "after", row["tokens_after"])
    else:
        print("turn", row["turn"], "tokens", row["tokens"], "server_input_tokens", row["usage"].get("input_tokens"))
folds = [row for row in out["token_trace"] if row.get("event") == "compact"]
print("compactions", len(folds))
print("last_summary", folds[-1]["summary"] if folds else None)
print("probe", PROBE)
print("probe_reply", out["replies"][-1])
