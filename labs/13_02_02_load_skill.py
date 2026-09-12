# %% [markdown]
# Write and load a DataFlow refund-policy Skill.
#
# When this works, the refund ask loads, the billing ask skips, a vague
# description steals the billing ask, and the committed description
# does not.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.skills.loader import load_skills, match

run_path = root / "dataflow" / "skills" / "runs" / "trigger.json"
committed_run = run_path.read_text(encoding="utf-8") if run_path.is_file() else ""

REFUND_ASK = "Please refund order DF-1001, the lamp is unused"
BILLING_ASK = "How much is an extra user on Professional?"

print("model", config.CHAT_MODEL)
skills = load_skills()
print("skills", [row.get("name") for row in skills])
model = config.get_chat_model()
loaded = match(REFUND_ASK, skills, model=model)
skipped = match(BILLING_ASK, skills, model=model)
print("load", None if loaded is None else loaded.get("name"))
print("load_description", None if loaded is None else loaded.get("description"))
print("skip", "none" if skipped is None else skipped.get("name"))
print("skip_description", skills[0].get("description") if skills else None)

asks = [
    {
        "ticket": REFUND_ASK,
        "decision": "load" if loaded is not None else "skip",
        "skill": None if loaded is None else loaded.get("name"),
        "description": None if loaded is None else loaded.get("description"),
    },
    {
        "ticket": BILLING_ASK,
        "decision": "skip" if skipped is None else "load",
        "skill": "none" if skipped is None else skipped.get("name"),
        "description": skills[0].get("description") if skills else None,
    },
]
run_path.parent.mkdir(parents=True, exist_ok=True)
run_path.write_text(json.dumps({"asks": asks}, indent=2) + "\n", encoding="utf-8")
print("wrote", run_path.as_posix())
print(run_path.read_text(encoding="utf-8"))

# %%
print("cell", "break")
print("BREAK: a planted vague description steals the billing ask")
vague = dict(skills[0])
vague["description"] = "Use for customer money questions"
stolen = match(BILLING_ASK, [vague], model=model)
print("vague_description", vague["description"])
print("stolen", None if stolen is None else stolen.get("name"))
print("stolen_on_billing", stolen is not None)

# %%
print("cell", "fix")
print("FIX: the committed description skips billing")
fixed = match(BILLING_ASK, skills, model=model)
print("fixed", "none" if fixed is None else fixed.get("name"))
print("fixed_skips_billing", fixed is None)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_run:
    run_path.write_text(committed_run, encoding="utf-8")
print("restored_trigger", bool(committed_run))
