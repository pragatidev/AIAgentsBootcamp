# %% [markdown]
# What you gain and lose versus LangGraph.
#
# When this works, the rubric has a row per product including LangGraph,
# every cell is filled, every path exists, and every row has a loss.
# A planted empty LangGraph lose cell fails the check. The committed
# table passes. Focus column: when not.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

rubric_path = root / "labs" / "16_compare" / "rubric.md"
committed = rubric_path.read_text(encoding="utf-8")

REQUIRED = [
    "product",
    "interrupt",
    "checkpointer",
    "tests",
    "package",
    "human gate",
    "gain",
    "lose",
    "when not",
    "path",
]
PRODUCTS = [
    "Langflow",
    "n8n",
    "CrewAI",
    "AutoGen",
    "OpenAI Agents SDK",
    "Google ADK",
    "LangGraph",
]


def parse_rubric(text: str) -> tuple[list[dict], list[str]]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        return [], []
    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows, headers


def check(text: str) -> list[str]:
    fails = []
    rows, headers = parse_rubric(text)
    if "when not" not in headers:
        fails.append("missing when not column")
    for name in REQUIRED:
        if name not in headers:
            fails.append("missing column " + name)
    names = [row.get("product", "") for row in rows]
    if names != PRODUCTS:
        fails.append("products " + json.dumps(names))
    if len(rows) != 7:
        fails.append("expected 7 rows, got " + str(len(rows)))
    for row in rows:
        product = row.get("product", "")
        for key, value in row.items():
            if value == "":
                fails.append("empty cell " + product + " " + key)
        lose = row.get("lose", "")
        if not lose:
            fails.append("no loss " + product)
        path = row.get("path", "")
        if path:
            target = root / path
            if not target.exists():
                fails.append("missing path " + path)
    return fails


print("cue", "when not")
print("headers", parse_rubric(committed)[1])
print("table")
print(committed)

# %%
print("cell", "break")
print("BREAK: planted empty LangGraph lose cell")
rows, headers = parse_rubric(committed)
lose_idx = headers.index("lose")
planted_lines = []
for ln in committed.splitlines():
    if ln.strip().startswith("| LangGraph |"):
        cells = [c for c in ln.split("|")]
        # cells[0] is leading empty from split
        body = [c for c in ln.strip().split("|")]
        parts = ln.split("|")
        # '| product | interrupt | ...' -> index 1 is product, lose is lose_idx+1
        parts[lose_idx + 1] = " "
        planted_lines.append("|".join(parts))
    else:
        planted_lines.append(ln)
planted = "\n".join(planted_lines)
if not planted.endswith("\n"):
    planted = planted + "\n"
rubric_path.write_text(planted, encoding="utf-8")
plant_fails = check(planted)
print("plant_fails")
for item in plant_fails:
    print("-", item)
print("plant_failed", bool(plant_fails))

# %%
print("cell", "fix")
print("FIX: restore the committed table with a LangGraph loss")
rubric_path.write_text(committed, encoding="utf-8")
fix_fails = check(committed)
print("fix_fails", fix_fails)
print("fix_passed", fix_fails == [])
print("rows", len(parse_rubric(committed)[0]))
for row in parse_rubric(committed)[0]:
    print("row", row["product"], "lose", row["lose"][:80])
    print("when not", row["when not"])
    print("path", row["path"])

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
rubric_path.write_text(committed, encoding="utf-8")
print("restored_rubric", rubric_path.read_text(encoding="utf-8") == committed)
