# %%
"""S10.4 Trim keeps the last N. No model."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage, HumanMessage, trim_messages

from dataflow.graphs.trim import count_message_tokens

# %%
messages = [
    HumanMessage(content="ticket DF-1001"),
    AIMessage(content="looked up desk lamp"),
    HumanMessage(content="policy 30 days"),
    AIMessage(content="human asked again"),
    HumanMessage(content="ticket DF-1002"),
    AIMessage(content="looked up mug"),
]
print("before", count_message_tokens(messages))
kept = trim_messages(
    messages,
    max_tokens=40,
    token_counter=count_message_tokens,
    strategy="last",
)
print("after", [str(m.content) for m in kept])
print("keep_tokens", 40)
