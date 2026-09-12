# %% [markdown]
# Evaluator-optimizer on a TalentFlow email.
#
# When this works, the rubric is the first file, the bar and the cap
# are the first two numbers, and each attempt prints a score and a
# rewrite line, then the stop reason. The break is a loop with no cap.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from talentflow.graphs.eval_optimize import RUBRIC_PATH, run_eval_optimize
from talentflow.graphs.score_resumes import load_resumes

print("model", config.CHAT_MODEL)
print("rubric_path", RUBRIC_PATH.as_posix())
rubric_text = RUBRIC_PATH.read_text(encoding="utf-8")
print("rubric")
print(rubric_text)
rubric = json.loads(rubric_text)
print("bar", rubric["bar"])
print("cap", rubric["cap"])

loaded = load_resumes()
row = next(r for r in loaded["resumes"] if r["name"] == "Sarah Chen")
print("candidate", row["name"])

out = run_eval_optimize(
    name=row["name"],
    resume=row["text"],
    job=loaded["job"],
)
print("attempts")
for item in list(out.get("history") or []):
    print("attempt", item.get("attempt"))
    print("scores", item.get("scores"))
    print("rewrite_first_line", item.get("first_line"))
print("stop", out.get("stop_reason"))

# %%
print("cell", "break")
print("BREAK: planted loop has no cap")
from tests.fixtures.fake_model import FakeChatModel

CEILING = 6
LOW = {
    "names_the_candidate": 0.2,
    "names_the_role": 0.2,
    "cites_one_resume_skill": 0.2,
    "under_180_words": 1.0,
    "total": 0.3,
}
# Fixture judge that never clears the bar, so the missing cap is visible.
cut = run_eval_optimize(
    name=row["name"],
    resume=row["text"],
    job=loaded["job"],
    model=FakeChatModel(
        reply="Hi there, we liked your file.",
        structured={"Scores": LOW},
    ),
    no_cap=True,
    hard_ceiling=CEILING,
)
print("no_cap_attempts")
for item in list(cut.get("history") or []):
    print("attempt", item.get("attempt"))
    print("scores", item.get("scores"))
    print("rewrite_first_line", item.get("first_line"))
print("no_cap_stop", cut.get("stop_reason"))
print("the loop was cut at", cut.get("attempts"))

# %%
print("cell", "fix")
print("FIX: the cap and the printed stop reason")
print("cap", rubric["cap"])
print("stop", out.get("stop_reason"))
