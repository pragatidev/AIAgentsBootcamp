# %% [markdown]
# Strip PII on a DataFlow ticket, then catch a secret.
#
# When this works, the email is redacted, the fake key is still in the
# first export, and SecretFilterMiddleware plus the export test go green.

# %%
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.guardrails.pii import export_trace, run_pii_ticket

print("model", config.CHAT_MODEL)
ticket = (
    "Hi, I am jordan@dataflow.example about order DF-1001. "
    "My test key is sk-abcdefghijklmnopqrstuvwxyz1234 and it should not leak."
)
print("ticket", ticket)

before_path = root / "dataflow" / "guardrails" / "runs" / "pii_before.jsonl"
after_path = root / "dataflow" / "guardrails" / "runs" / "pii_after.jsonl"
committed_before = (
    before_path.read_text(encoding="utf-8") if before_path.is_file() else ""
)
committed_after = after_path.read_text(encoding="utf-8") if after_path.is_file() else ""

# %%
print("cell", "pii_without_secret_filter")
before = run_pii_ticket(ticket, secret_filter=False)
print("messages_the_model_saw")
for msg in before["messages"]:
    content = getattr(msg, "content", None)
    print(type(msg).__name__, content)
export_trace(before_path, before["messages"])
print("export_before")
print(before_path.read_text(encoding="utf-8"))
print("email_redacted", "jordan@dataflow.example" not in before_path.read_text(encoding="utf-8"))
print("key_still_in_export", "sk-abcdefghijklmnopqrstuvwxyz1234" in before_path.read_text(encoding="utf-8"))

# %%
print("cell", "pii_with_secret_filter")
os.environ["DATAFLOW_PII_EXPORT"] = str(after_path)
after = run_pii_ticket(ticket, secret_filter=True)
export_trace(after_path, after["messages"])
print("export_after")
print(after_path.read_text(encoding="utf-8"))
print("key_gone", "sk-" not in after_path.read_text(encoding="utf-8"))

red = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_guardrails_pii.py::test_export_has_no_sk_key",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    env={**os.environ, "DATAFLOW_PII_EXPORT": str(before_path)},
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("red_on_before_export")
print(red.stdout)
print("red_exit", red.returncode)

green = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_guardrails_pii.py::test_export_has_no_sk_key",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    env={**os.environ, "DATAFLOW_PII_EXPORT": str(after_path)},
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("green_on_after_export")
print(green.stdout)
print("green_exit", green.returncode)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_before:
    before_path.write_text(committed_before, encoding="utf-8")
if committed_after:
    after_path.write_text(committed_after, encoding="utf-8")
print("restored_pii_exports", bool(committed_before or committed_after))
