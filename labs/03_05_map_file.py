# %%
"""Lab 5.5: rewrite a fat instruction file into a map.

What we build: the DataFlow desk's fat instruction file pastes six whole documents in front of
every ticket. You write the short file that replaces it, dataflow/context/MAP.md: a role, a scope,
the tool rules, the refusal, and one line per document saying when to open it. Then you type
check_map, which reads your file and names every line that points at something the desk cannot
open. No model runs here; lab 5.6 sends both files to the model.

What you learn: the always-on file is a table of contents, and every line in it is a promise that
a read will work. You see the size difference as numbers you produced.

What will be true on your screen: map_problems [] for a clean map, the map's size in characters
and tokens beside the fat file's (58,816 characters), and one line per map entry.
Run python -m pytest tests/test_lab_03_05.py -q to test your check.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import _ALLOWED_NAMES, count_tokens, repo_path
from dataflow.context.map_text import MAP_PATH, get_fat, load_map

FAT_PATH = root / "dataflow" / "context" / "FAT.md"


# %%
# TYPE THIS: check_map. Its finished copy is in dataflow/context/map_text.py.
def check_map(text: str) -> list[str]:
    """One problem per map entry a desk could not use: no bar, no when, or a file read_file cannot open."""
    problems = []
    for line in text.split("Map:", 1)[-1].splitlines():
        if not line.strip():
            continue
        name, bar, when = line.partition(" | ")
        name = name.strip()
        if not bar or "when" not in when.lower():
            problems.append(line + ": needs a name, a bar and a when")
        elif name not in _ALLOWED_NAMES or not _ALLOWED_NAMES[name].is_file():
            problems.append(name + ": not readable")
    return problems


# %%
# The fat file is built from the six documents; it is written only when it would change.
fat = get_fat()
if not FAT_PATH.is_file() or FAT_PATH.read_text(encoding="utf-8") != fat:
    FAT_PATH.write_text(fat, encoding="utf-8")
print("fat_file", repo_path(FAT_PATH))
print("fat_chars", len(fat))
print("fat_tokens", count_tokens([{"role": "system", "content": fat}]))

# %%
# Your map, read from the file you wrote. This lab never writes MAP.md.
# BREAK: add the line "refund_policy.md | when the customer asks for a refund" at the end of
# MAP.md and run. There is no such file (the refund rules live in return_policy.md), so the check
# names it. Delete the line and run again.
text = load_map()
print("map_file", repo_path(MAP_PATH))
for line in text.split("Map:", 1)[-1].splitlines():
    if line.strip():
        print("map_entry", line)
print("map_chars", len(text))
print("map_tokens", count_tokens([{"role": "system", "content": text}]))
print("map_problems", check_map(text))
