# %% [markdown]
# Portfolio walkthrough of the three worlds.
#
# When this works, README, the tests folder and deploy/smoke.py are
# opened for TechCorp, DataFlow and TalentFlow, the refuse line prints,
# pytest with no key prints its last line, and a README that claims
# four clouds is explained as a clone fail. The committed README is
# not rewritten by this lab.

# %%
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

readme_path = root / "README.md"
committed_readme = readme_path.read_text(encoding="utf-8")
tests_dir = root / "tests"
smoke_path = root / "deploy" / "smoke.py"

WORLDS = (
    {
        "name": "techcorp",
        "readme": root / "techcorp" / "README.md",
        "tests_glob": "test_techcorp*.py",
    },
    {
        "name": "dataflow",
        "readme": readme_path,
        "tests_glob": "test_dataflow*.py",
    },
    {
        "name": "talentflow",
        "readme": root / "talentflow" / "README.md",
        "tests_glob": "test_talentflow*.py",
    },
)

print("tests_folder", tests_dir.as_posix(), tests_dir.is_dir())
print("smoke", smoke_path.as_posix(), smoke_path.is_file())
print("smoke_head")
print("\n".join(smoke_path.read_text(encoding="utf-8").splitlines()[:12]))

for world in WORLDS:
    print("world", world["name"])
    readme = world["readme"]
    print("readme", readme.as_posix(), readme.is_file())
    matches = sorted(p.name for p in tests_dir.glob(world["tests_glob"]))
    print("tests_matching", matches)
    print("smoke_for_world", smoke_path.is_file())

print("cell", "refuse_line")
refuse_line = ""
for line in committed_readme.splitlines():
    if "refuses when the knowledge base has nothing" in line.lower():
        refuse_line = line
        break
if not refuse_line:
    for line in committed_readme.splitlines():
        if "refuse" in line.lower() and "desk" in line.lower():
            refuse_line = line
            break
print("refuse_line", refuse_line)

# %%
print("cell", "pytest_no_key")
env = os.environ.copy()
env.pop("OPENAI_API_KEY", None)
env.pop("ANTHROPIC_API_KEY", None)
proc = subprocess.run(
    [sys.executable, "-m", "pytest"],
    cwd=str(root),
    env=env,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
out = (proc.stdout or "") + (proc.stderr or "")
print(out)
lines = [line for line in out.splitlines() if line.strip()]
last = lines[-1] if lines else ""
print("pytest_exit", proc.returncode)
print("pytest_last_line", last)

# %%
print("cell", "four_clouds_break")
bad_readme = (
    committed_readme
    + "\n\nDeployed to AWS, Azure, GCP, and IBM Cloud. Four clouds.\n"
)
print("bad_readme_is_a_string", True)
print("bad_readme_written_to_disk", False)
print("four_clouds_claim", "AWS, Azure, GCP, and IBM Cloud")
print(
    "why_a_clone_fails",
    "A README that claims four clouds fails a clone because those "
    "clouds are not in this repo. deploy/smoke.py hits local /health. "
    "pytest -q is the contract with no cloud key. A hiring manager who "
    "clones will not find AWS, Azure, GCP, or IBM Cloud, and the refuse "
    "line they needed is buried under a claim the suite cannot prove.",
)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
now = readme_path.read_text(encoding="utf-8")
if now != committed_readme:
    readme_path.write_text(committed_readme, encoding="utf-8")
    print("restored_readme", True)
else:
    print("readme_unchanged", True)
print("no committed file mutated")
