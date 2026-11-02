# %%
"""Lab 5.14: add a just-in-time file read.

What we build: you type read_file, the one tool the desk gets, with a list of the files it may
open. The map tells the model which file goes with which question. Two tickets, a return and a
shipping question, run on that desk; then the same return ticket on a desk with every file pasted
in. Then you call your read_file by hand on a path that tries to climb out, on the employee
handbook, and on the handbook again with the customer desk's list.

What you learn: just-in-time retrieval in your own code: carry the catalogue, fetch the book. And
that the list in code is the real control, not the "never" written in the map.

What will be true on your screen: the return ticket reads ['return_policy.md'], the shipping
ticket reads ['shipping.md'], both counts for each desk, read_only_on_match True; then unknown
file for ../../.env, the handbook found, and the handbook refused once the list is passed.
Run python -m pytest tests/test_lab_03_14.py -q to test your read_file.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import (
    _ALLOWED_NAMES,
    CUSTOMER_FILES,
    ContextAgent,
    applied_window,
    chat_caller,
    context_caller,
)
from dataflow.context.map_text import get_fat, load_map

# The window for every desk here. It has to hold the pasted-in desk's fat file.
WINDOW = 16384
RETURN_TICKET = "What is your return window for a delivered desk lamp?"
SHIP_TICKET = "How many business days is standard shipping inside the country?"
HANDBOOK_TICKET = "What does your employee handbook say about returning company equipment?"


# %%
# TYPE THIS: read_file. Its finished copy is in dataflow/context/agent.py, with the list.
# BREAK: delete the two lines that check allowed and run. The last direct call below finds the
# handbook. Put them back and run again.
def read_file(path: str, allowed=None) -> str:
    """Read a file by its map name. Only the last part of the path counts; a name outside allowed is refused."""
    name = Path(str(path or "").strip()).name
    target = _ALLOWED_NAMES.get(name)
    if target is None or not target.is_file():
        return json.dumps({"found": False, "path": name, "reason": "unknown file"})
    if allowed is not None and name not in allowed:
        return json.dumps({"found": False, "path": name, "reason": "not on this desk's list"})
    text = target.read_text(encoding="utf-8")
    if len(text) > 4000:
        text = text[:4000] + "\n...[truncated]"
    return json.dumps({"found": True, "path": name, "text": text})


def run_desk(name: str, agent: ContextAgent, ticket: str) -> dict:
    out = agent.run(ticket)
    calls = [row for row in out["token_trace"] if row.get("event") == "model"]
    print(name + "_tools", out["tool_names"])
    print(name + "_reads", out["reads"])
    print(name + "_final", out["final"])
    print(name + "_last_call", "library_tokens", calls[-1]["tokens"], "server_input_tokens", calls[-1]["usage"].get("input_tokens"))
    return out


def jit_desk(reader=read_file) -> ContextAgent:
    return ContextAgent(
        context_caller(enable_read=True, enable_notes=False, num_ctx=WINDOW),
        system=load_map(),
        cap=6,
        reader=reader,
    )


# %%
ret = run_desk("return_ticket", jit_desk(), RETURN_TICKET)
ship = run_desk("ship_ticket", jit_desk(), SHIP_TICKET)
pre = run_desk("preload", ContextAgent(chat_caller(num_ctx=WINDOW), system=load_map(), preload=get_fat()), RETURN_TICKET)
print("window", WINDOW)
print("window_applied", applied_window())
print("read_only_on_match", ret["reads"] == ["return_policy.md"] and ship["reads"] == ["shipping.md"])

# %%
# Your read_file, called by hand. No model.
print("climb_out", read_file("../../.env"))
print("handbook", json.loads(read_file("employee_handbook.txt"))["found"])
print("handbook_on_the_customer_list", read_file("employee_handbook.txt", allowed=CUSTOMER_FILES))

# %%
# The same question from a customer, to the model, before and after the list.
for name, reader in (("open", read_file), ("customer", lambda path: read_file(path, allowed=CUSTOMER_FILES))):
    out = jit_desk(reader).run(HANDBOOK_TICKET)
    results = [json.loads(m["content"]) for m in out["messages"] if m.get("role") == "tool"]
    print(name + "_desk_reads", out["reads"])
    print(name + "_desk_results", [(r.get("path"), r.get("found"), r.get("reason")) for r in results])
    print(name + "_desk_final", out["final"])
