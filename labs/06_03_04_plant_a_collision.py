# %% [markdown]
# Plant a collision, read the error, then fix it with a reducer.
#
# `python labs/06_03_04_plant_a_collision.py --plant` raises
# InvalidUpdateError. Without the flag, both log lines land.

# %%
from pathlib import Path
import argparse
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.errors import InvalidUpdateError

from dataflow.graphs.collision import build_collision, build_collision_fixed

parser = argparse.ArgumentParser()
parser.add_argument("--plant", action="store_true")
args, _ = parser.parse_known_args()
print("plant", args.plant)

# %%
if args.plant:
    try:
        build_collision().invoke({"ticket": "DF-1001", "log": ""})
        print("collision", "unexpected_success")
    except InvalidUpdateError as exc:
        print("collision", type(exc).__name__)
        print(str(exc).split("\n")[0])
else:
    out = build_collision_fixed().invoke({"ticket": "DF-1001", "log": []})
    for line in out.get("log") or []:
        print("log", line)
