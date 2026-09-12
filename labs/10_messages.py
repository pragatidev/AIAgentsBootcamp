# %%
"""S10.3 add_messages keeps both turns."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage

from dataflow.graphs.messages import build_messages_graph
from tests.fixtures.fake_model import FakeChatModel

# %%
out = build_messages_graph(model=FakeChatModel()).invoke(
    {"messages": [HumanMessage(content="Can I return order DF-1001?")]}
)
kinds = [m.type for m in out["messages"]]
texts = [str(m.content) for m in out["messages"]]
print("kept", len(out["messages"]))
print("kinds", kinds)
print("texts", texts)
