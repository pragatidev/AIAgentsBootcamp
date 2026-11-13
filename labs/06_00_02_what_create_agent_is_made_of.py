# %%
"""Lab 9.2: what create_agent is made of.

What we build: nothing new. You build the Section 4 TechCorp desk again with create_agent, exactly as lab
4.12 did, and the package's desk with its gate from lecture 4.14, and you ask each one what it is. Then you
ask Deep Agents what its builder promises to return. No model is called, no deep agent is built, and no
other framework is imported.

What you learn: the two higher-level agents you have met or will meet are LangGraph graphs. create_agent
hands back a compiled LangGraph StateGraph with a model node, a tools node and the loop between them; its
middleware hooks are nodes on the same graph; and create_deep_agent declares the same class as its return
type. So moving down to LangGraph costs no rewrite of your tools or prompts.

What will be true on your screen: the model line, the langchain-core and langgraph versions, then for the
create_agent desk the module and name of its type (langgraph.graph.state CompiledStateGraph on the pin),
its nodes and its drawing; the package desk's nodes with the two middleware nodes; and create_deep_agent's
declared return type, with a line saying whether it is the same class.
"""

from importlib.metadata import version
import inspect
from pathlib import Path
import sys
import typing

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from deepagents import create_deep_agent
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk
from techcorp.agent.prompts import DESK_SYSTEM_PROMPT
from techcorp.tools.accounts import grant_access, lookup_user, reset_password

# The model is built but never called in this lab.
chat = config.get_chat_model(reasoning=False)
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

# %%
# The desk you typed in lab 4.12: one call.
desk = create_agent(
    model=chat,
    tools=[lookup_user, reset_password, grant_access],
    system_prompt=DESK_SYSTEM_PROMPT,
    context_schema=DeskContext,
)
print("desk_type", type(desk).__module__, type(desk).__name__)
print("is_compiled_state_graph", isinstance(desk, CompiledStateGraph))
print("nodes", list(desk.get_graph().nodes))
print(desk.get_graph().draw_mermaid())

# %%
# The package's desk, with the write gate and the tool call limit from lecture 4.14: each hook is a node.
gated = build_techcorp_desk(model=chat)
print("package_desk_type", type(gated).__module__, type(gated).__name__)
print("package_desk_nodes", list(gated.get_graph().nodes))

# %%
# Deep Agents: read the return type its builder declares. Nothing is built.
declared = inspect.signature(create_deep_agent).return_annotation
print("create_deep_agent returns", declared)
print("same_class", (typing.get_origin(declared) or declared) is CompiledStateGraph)
