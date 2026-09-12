# %% [markdown]
# Rewrite a fat instruction file into a map.
#
# FAT is the encyclopedia. MAP is twelve lines of name plus when.
# Both are written to dataflow/context/ as .md files.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.map_text import MAP, get_fat, map_lines

FAT = get_fat()
CONTEXT = root / "dataflow" / "context"

# %%
print("MAP")
print(MAP)
print("map_lines", len(map_lines()))
for line in map_lines():
    print("map_entry", line)

# %%
fat_path = CONTEXT / "FAT.md"
map_path = CONTEXT / "MAP.md"
fat_path.write_text(FAT, encoding="utf-8")
map_path.write_text(MAP, encoding="utf-8")
print("wrote", fat_path.as_posix())
print("fat_chars", len(FAT))
print("wrote", map_path.as_posix())
print("map_chars", len(MAP))
