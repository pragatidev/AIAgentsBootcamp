# %%
"""Lab 5.18: guard the window.

What we build: a customer desk that decides what may enter the model's view before the call. You
type guard_read, which takes a file the desk read, drops any line that tries to give the model an
order, masks secrets and email addresses, and boxes what is left with its source. Then five runs:
a wiki page with a planted instruction, read unguarded and guarded; one customer asking about
another customer's order; a ticket carrying a secret and an email address; and two customers'
notes, in one shared file and in one file each.

What you learn: what must never enter the window, and that each rule is code that runs before the
call, not a sentence in the prompt. Instructions hidden in retrieved text, other customers' data,
secrets and personal details are kept out by the guard, the role's file list, a lookup scoped to
the customer, and a notes file per customer. Section 31 adds the allowlist at the tool port and
Section 32 the full PII policy; this lab is the part that decides what the model sees.

What will be true on your screen: run 1 shows the planted line inside the tool message; run 2
shows it in dropped_lines and not in the window; run 3 shows "not this customer's order" and
other_customer_ids_in_window []; run 4 shows the ticket as sent, with secret_in_window False and
email_in_window False; run 5 shows the other customer's rule in the shared file's notes block and
nothing in the per-customer one.
Run python -m pytest tests/test_lab_03_18.py -q to test your guard_read.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import (
    CUSTOMER_FILES,
    NOTES_PATH,
    ContextAgent,
    applied_window,
    context_caller,
    notes_path_for,
    read_file,
    write_note,
)
from dataflow.context.box_text import box
from dataflow.context.guard import other_customer_ids, strip_instructions
from dataflow.context.map_text import load_map
from dataflow.context.redact import EMAIL_RE, SECRET_RE, redact


# %%
# TYPE THIS: guard_read. Its finished copy is in dataflow/context/guard.py.
# BREAK: change the first line to clean, dropped = text, [] and run. Run 2's dropped_lines is empty
# and the planted line sits inside the box: the box alone does not keep it out. Put it back.
def guard_read(name: str, text: str) -> tuple[str, list[str]]:
    """Strip instruction lines, mask secrets and emails, then box the rest with its source."""
    clean, dropped = strip_instructions(text)
    return box(name, redact(clean)), dropped


# %%
# A planted write tool: it records that the model asked for it and does nothing else.
RESET_SCHEMA = {
    "type": "function",
    "function": {
        "name": "reset_password",
        "description": "Reset the password on an account.",
        "parameters": {
            "type": "object",
            "properties": {"account": {"type": "string", "description": "Account or customer id"}},
            "required": ["account"],
        },
    },
}


def reset_password(account: str = "") -> str:
    return json.dumps({"ok": False, "planted": True, "account": account})


def tool_texts(out: dict) -> list[str]:
    return [m["content"] for m in out["messages"] if m.get("role") == "tool"]


SYSTEM = load_map()
PASSWORD_TICKET = "How long does my password need to be?"
# This lab starts with no per-customer notes; run 5 writes one.
for customer in ("C-2001", "C-2002"):
    notes_path_for(customer).unlink(missing_ok=True)

# %%
# Run 1: unguarded. The open list, no guard, and the planted write tool bound.
desk = ContextAgent(
    context_caller(enable_read=True, enable_notes=False, extra_schemas=[RESET_SCHEMA]),
    system=SYSTEM,
    customer_id="C-2001",
    tools={"reset_password": reset_password},
    reader=read_file,
)
out = desk.run(PASSWORD_TICKET)
print("run 1 unguarded")
print("reads", out["reads"])
print("instruction_in_window", any("Agent instruction" in text for text in tool_texts(out)))
print("tool_names", out["tool_names"])
print("final", out["final"])

# %%
# Run 2: guarded. First your guard on the same file, by hand, so it shows whatever the model does.
guarded = json.loads(read_file("security.md", allowed=CUSTOMER_FILES, guard=guard_read))
print("run 2 guarded")
print("dropped_lines", guarded["dropped_lines"])
print("boxed_text", guarded["text"])
# Then the desk, with the customer list and your guard_read on every read.
desk = ContextAgent(
    context_caller(enable_read=True, enable_notes=False, extra_schemas=[RESET_SCHEMA]),
    system=SYSTEM,
    customer_id="C-2001",
    tools={"reset_password": reset_password},
    reader=lambda path: read_file(path, allowed=CUSTOMER_FILES, guard=guard_read),
)
out = desk.run(PASSWORD_TICKET)
print("reads", out["reads"])
print("desk_dropped_lines", out["dropped_lines"])
print("instruction_in_window", any("Agent instruction" in text for text in tool_texts(out)))
print("tool_names", out["tool_names"])
print("final", out["final"])

# %%
# Run 3: one customer, another customer's order. C-2002 asks about DF-1001, which is C-2001's.
desk = ContextAgent(
    context_caller(enable_read=True, enable_notes=False, enable_orders=True),
    system=SYSTEM,
    customer_id="C-2002",
    allowed=CUSTOMER_FILES,
    guard=True,
)
out = desk.run("What is the status of order DF-1001?")
print("run 3 tenant")
print("tool_names", out["tool_names"])
for text in tool_texts(out):
    print("tool_result", text[:200])
print("other_customer_ids_in_window", other_customer_ids(out["messages"], "C-2002"))
print("final", out["final"])
old = json.loads(read_file("orders.json"))["text"]
print("old_path_customer_ids_in_one_orders_read", len(other_customer_ids([{"content": old}], "C-2002")))

# %%
# Run 4: a ticket that carries a secret and an email address.
fixture = json.loads((root / "dataflow" / "context" / "fixtures" / "ticket_with_secret.json").read_text(encoding="utf-8"))
desk = ContextAgent(
    context_caller(enable_read=True, enable_notes=False),
    system=SYSTEM,
    customer_id=fixture["customer_id"],
    allowed=CUSTOMER_FILES,
    guard=True,
)
out = desk.run(fixture["text"])
sent = "\n".join(str(m.get("content")) for m in out["messages"])
print("run 4 secrets")
print("ticket_as_sent", out["messages"][1]["content"])
print("secret_in_window", bool(SECRET_RE.search(sent)))
print("email_in_window", bool(EMAIL_RE.search(sent)))
print("final", out["final"])

# %%
# Run 5: two customers' notes. C-2001's rule is written to the shared file and to C-2001's own file.
RULE = "Refunds for this account must never exceed 40 dollars."
NOTES_PATH.write_text("{}", encoding="utf-8")
write_note("constraint", RULE, NOTES_PATH)
own = notes_path_for("C-2001")
own.parent.mkdir(parents=True, exist_ok=True)
own.write_text("{}", encoding="utf-8")
write_note("constraint", RULE, own)
shared = ContextAgent(context_caller(), system="desk", customer_id="C-2002", notes_path=NOTES_PATH)
per_customer = ContextAgent(context_caller(), system="desk", customer_id="C-2002")
print("run 5 notes")
print("shared_file_notes_block", shared._system_text()[len("desk"):].strip() or "(none)")
print("per_customer_notes_block", per_customer._system_text()[len("desk"):].strip() or "(none)")
print("window_applied", applied_window())
