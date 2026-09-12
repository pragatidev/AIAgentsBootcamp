# %% [markdown]
# Replace a SaaS seat, honestly.
#
# When this works, business/saas_replace.md prints, names a leftover
# seat, has no currency symbol and none of the banned income words.
# A variant that says the agent deletes the ATS fails.

# %%
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

page_path = root / "business" / "saas_replace.md"
committed = page_path.read_text(encoding="utf-8")
print("page", page_path.as_posix())
print(committed)

BANNED = re.compile(r"\b(earn|income|revenue|profit|guaranteed)\b", re.I)
CURRENCY = re.compile(r"[$€£¥₹¢]")


def check_page(text: str) -> dict:
    leftover = "leftover seat: the ats" in text.lower()
    currency = bool(CURRENCY.search(text))
    banned = sorted({m.group(1).lower() for m in BANNED.finditer(text)})
    deletes = "deletes the ats" in text.lower() or "delete the ats" in text.lower()
    ok = leftover and not currency and not banned and not deletes
    return {
        "leftover_seat": leftover,
        "currency": currency,
        "banned": banned,
        "deletes_ats": deletes,
        "ok": ok,
    }


print("cell", "mechanical_check")
report = check_page(committed)
print("leftover_seat", report["leftover_seat"])
print("currency_symbol", report["currency"])
print("banned_words", report["banned"])
print("page_ok", report["ok"])

# %%
print("cell", "deletes_ats_break")
bad = (
    "TalentFlow deletes the ATS. The agent takes recruiting SaaS down. "
    "No leftover seat remains."
)
print("variant", bad)
bad_report = check_page(bad)
print("variant_leftover_seat", bad_report["leftover_seat"])
print("variant_deletes_ats", bad_report["deletes_ats"])
print("variant_ok", bad_report["ok"])
print(
    "why_that_page_fails",
    "A page that says the agent deletes the ATS fails because TalentFlow "
    "does not take the ATS down. The leftover seat (interview scheduling, "
    "offer letters, compliance) is unnamed, and keep versus replace is gone. "
    "The honest page names the leftover seat and keeps it.",
)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
now = page_path.read_text(encoding="utf-8")
if now != committed:
    page_path.write_text(committed, encoding="utf-8")
    print("restored_page", True)
else:
    print("page_unchanged", True)
print("no committed file mutated")
