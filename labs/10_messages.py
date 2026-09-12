# %%
"""S10.3 add_messages keeps both turns."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.graphs.messages import build_chat

# %%
out = build_chat().invoke({"messages": []})
kinds = [m.type for m in out["messages"]]
texts = [str(m.content) for m in out["messages"]]
print("kept", len(out["messages"]))
print("kinds", kinds)
print("texts", texts)
