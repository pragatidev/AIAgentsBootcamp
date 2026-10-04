# %% [markdown]
# Notebooks and lab files.
#
# A lab is a `.py` with `# %%` cells, and most have a notebook twin
# from `python scripts/make_twins.py`. Run this file cell by cell, or
# as a script. The twin has four code cells: a boot cell that finds
# the repo root, then these three, and each of them prints.

# %%
print("cell", 1)
print("open this file in VS Code and use Run Cell on each block")

# %%
print("cell", 2)
print("the notebook twin of this file is labs/00_05_notebook_twin_demo.ipynb")

# %%
print("cell", 3)
print("a lab is checked by running the file and by pytest on the helpers")
