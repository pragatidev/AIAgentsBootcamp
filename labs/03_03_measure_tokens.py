# %%
"""Lab 5.3: measure tokens before and after the death.

What we build: you type measure, the four lines that count a message list with a tokenizer on
your machine. Then we open the trace lab 5.2 saved and count two turns of each run: the turn
where the rule was stated and the probe turn that needed it. Each one is counted twice, by your
measure and by the number the model server reported.

What you learn: the two counts from Section 2 in a real run. The library count is how you plan;
the server count is what the model read and what the window holds. When the server's number sits
at the window while yours is above it, the server cut the start of the conversation.

What will be true on your screen: for run A and run B, the window, both counts at the rule's
turn and at the probe, and cut_by_server: False for run A, True for run B. If lab 5.2 has not
run yet, one line telling you to run it first.
Run python -m pytest tests/test_lab_03_03.py -q to test your measure.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import tiktoken

from dataflow.context.agent import repo_path
from dataflow.context.rot import ROT_TRACE, cut_by_server, pick_rows

# BREAK: change this to "o200k_base" and run. Your counts move; the server's do not, because the
# server counts with the model's own tokenizer. Put "cl100k_base" back.
ENCODING = "cl100k_base"


# %%
# TYPE THIS: measure. Its finished copy is count_tokens in dataflow/context/agent.py.
def measure(messages: list) -> int:
    enc = tiktoken.get_encoding(ENCODING)
    text = "\n".join(str(m.get("role") or "") + "\n" + str(m.get("content") or "") for m in messages)
    return len(enc.encode(text))


# %%
if not ROT_TRACE.is_file():
    print("missing_rot_trace", repo_path(ROT_TRACE))
    print("run labs/03_02_context_rot.py first")
    from labs._quiet_exit import quiet_exit

    quiet_exit()

# %%
payload = json.loads(ROT_TRACE.read_text(encoding="utf-8"))
rule_turn = payload["constraint_turn"]
probe_turn = payload["probe_turn"]
print("encoding", ENCODING)
for name, run in payload["runs"].items():
    rows = pick_rows(run["trace"], probe_turn, rule_turn)
    window = run["window"]
    print("run", name, "window", "server default" if window is None else window)
    for label, turn, row in (("rule", rule_turn, rows["before"]), ("probe", probe_turn, rows["after"])):
        # Turn k was sent the system message and the first 2k - 1 messages after it.
        sent = run["messages"][: 2 * turn]
        library = measure(sent)
        server = (row.get("usage") or {}).get("input_tokens")
        print(label, "turn", turn, "library_tokens", library, "server_input_tokens", server)
    print("cut_by_server", cut_by_server(library, server, window))
