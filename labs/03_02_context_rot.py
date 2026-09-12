# %% [markdown]
# Show a run that dies of context rot.
#
# A constraint stated at turn 4 is needed at turn 30. Print the turn
# and the token count at the failure. If the model does not fail, print
# that honestly and lengthen the run once.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import ContextAgent, chat_caller, count_tokens
from dataflow.context.rot import (
    CONSTRAINT,
    build_turns,
    constraint_turn,
    failed_constraint,
)

SYSTEM = (
    "You are the DataFlow support desk. Answer in one short sentence. "
    "Obey every constraint the customer stated."
)

# %%
turns = build_turns(25)
print("turns", len(turns))
print("constraint_turn", constraint_turn())
print("constraint", CONSTRAINT)
agent = ContextAgent(chat_caller(), system=SYSTEM)
out = agent.run_turns(turns)
fail_turn = None
for row in out["token_trace"]:
    if row["turn"] == constraint_turn():
        print("tokens_at_constraint", row["tokens"], "usage", row["usage"])
    if row["turn"] >= 30 and failed_constraint(row["text"]):
        fail_turn = row["turn"]
        print("failed_at_turn", fail_turn)
        print("failed_reply", row["text"])
        print("tokens_at_failure", row["tokens"], "usage", row["usage"])
        break

# %%
if fail_turn is None:
    last = out["token_trace"][-1]
    print("did_not_fail", True)
    print("last_turn", last["turn"])
    print("last_reply", last["text"])
    print("lengthening_once", True)
    long_turns = build_turns(40)
    print("turns_lengthened", len(long_turns))
    agent2 = ContextAgent(chat_caller(), system=SYSTEM)
    out2 = agent2.run_turns(long_turns)
    out = out2
    fail_turn = None
    for row in out2["token_trace"]:
        if failed_constraint(row["text"]) and row["turn"] > constraint_turn():
            fail_turn = row["turn"]
            print("failed_at_turn", fail_turn)
            print("failed_reply", row["text"])
            print("tokens_at_failure", row["tokens"], "usage", row["usage"])
            break
    if fail_turn is None:
        last2 = out2["token_trace"][-1]
        print("did_not_fail_after_lengthen", True)
        print("last_turn", last2["turn"])
        print("last_reply", last2["text"])
        print("tokens_at_last", last2["tokens"], "usage", last2["usage"])

payload = {
    "fail_turn": fail_turn,
    "trace": out["token_trace"],
}
side = root / "dataflow" / "context" / "_last_rot.json"
side.write_text(json.dumps(payload, default=str), encoding="utf-8")
print("trace_saved", str(side))
print("final_message_tokens", count_tokens(out["messages"]))
