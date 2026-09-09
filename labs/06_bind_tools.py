# %%
"""S6.3 Read a typed tool. No model bind in the no-key path."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from northstar.tools.orders import lookup_order_tool

# %%
print("name", lookup_order_tool.name)
print("description", lookup_order_tool.description)
print("args", lookup_order_tool.args)
