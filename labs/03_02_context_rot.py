# %%
"""Lab 5.2: show a run that dies of context rot.

What we build: one long conversation with the DataFlow desk. At turn four the customer states a
hard rule, refunds on this account never go above 40 dollars, then asks twenty-five unrelated
questions, then asks for the lamp's full price back. You type the judge that reads the desk's
answer, and we run the same conversation twice: once on the server's full window, once on a
window set small on purpose.

What you learn: the window has an edge and nothing warns you when you cross it. The server keeps
the end of the conversation and cuts the start, so the rule said first is the first thing to go.
And "the model forgot" is a claim you check with code, not a feeling.

What will be true on your screen: turns 30, then for each run its window, the tokens at the
probe counted twice (by the library on your machine and by the server), the verdict and the
desk's reply. Run A has the whole conversation in view. Run B's server count sits at or under
512 while the library count is above it: the cut happened, and the verdict is the model's.
Run python -m pytest tests/test_lab_03_02.py -q to test your judge.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import ContextAgent, applied_window, chat_caller, count_tokens, repo_path
from dataflow.context.rot import CONSTRAINT, PROBE, ROT_TRACE, build_turns, names_cap, promises_over_cap


# %%
# TYPE THIS: judge. Its finished copy is judge_refund_reply in dataflow/context/rot.py.
def judge(text: str) -> str:
    """held: the cap is named and nothing above it is promised. contradicted: both. broke: the cap is not named."""
    if not names_cap(text):
        return "broke"
    if promises_over_cap(text):
        return "contradicted"
    return "held"


# %%
# The one knob: the window run B gets, in tokens. Run A gets the server's default.
WINDOW = 512

# BREAK: set CONSTRAINT_LAST = True and run. The rule is now said again just before the probe, so
# even run B's small window holds it; read run B's verdict. Then set it back to False.
CONSTRAINT_LAST = False

SYSTEM = (
    "You are the DataFlow support desk. Answer in one short sentence. "
    "Obey every constraint the customer stated."
)
turns = build_turns(25, constraint_last=CONSTRAINT_LAST)
rule_turn = turns.index(CONSTRAINT) + 1
print("turns", len(turns))
print("constraint_turn", rule_turn)
print("constraint", CONSTRAINT)
print("probe", PROBE)


def run(name: str, window: int | None) -> dict:
    print("run", name, "starts, one model call per turn")
    agent = ContextAgent(chat_caller(num_ctx=window, local=True), system=SYSTEM)
    out = agent.run_turns(turns, progress_every=10)
    rows = {row["turn"]: row for row in out["token_trace"]}
    probe = rows[len(turns)]
    print("run", name)
    print("window", "server default" if window is None else window)
    print("window_applied", applied_window())
    print("library_tokens_at_constraint", rows[rule_turn]["tokens"])
    print("server_input_tokens_at_constraint", rows[rule_turn]["usage"].get("input_tokens"))
    print("library_tokens_at_probe", probe["tokens"])
    print("server_input_tokens_at_probe", probe["usage"].get("input_tokens"))
    print("verdict", judge(probe["text"]))
    print("reply", probe["text"])
    return {"window": window, "trace": out["token_trace"], "messages": out["messages"]}


# %%
runs = {"A": run("A", None), "B": run("B", WINDOW)}

# %%
# Lab 5.3 reads this file. Git ignores it.
payload = {"window": WINDOW, "constraint_turn": rule_turn, "probe_turn": len(turns), "runs": runs}
ROT_TRACE.write_text(json.dumps(payload, default=str), encoding="utf-8")
print("trace_saved", repo_path(ROT_TRACE))
print("final_message_tokens", {name: count_tokens(r["messages"]) for name, r in runs.items()})
