# %%
"""Lab 4.5: write a typed tool with the @tool decorator.

What we build: the TechCorp desk's first tool, lookup_user, typed by you as a Python function with
@tool on it. Then we print exactly what a model is handed when the tool is bound, call it for a real
employee and for one who does not exist, and break it twice.

What you learn: a tool is a name, a description, an argument schema and a return, all made from one
decorated function. The model reads the description and the schema, never your code, and the return
is data, a hit or a typed miss, never an exception. reset_password's schema shows its runtime
parameter missing, because that one is not the model's to fill.

What will be true on your screen: no model is needed, so this runs with Ollama off. The name
lookup_user, your docstring as the description, a parameters block with one string field, query;
the record for E-4101; the typed miss for E-0000; and reset_password's parameters with user_id only.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool

from techcorp.tools.accounts import _find_user, _public_user, reset_password


# %%
# TYPE THIS: lookup_user. The decorator, the signature and the docstring are given; you type the body.
# Its finished copy is in techcorp/tools/accounts.py, where the desk and Section 39 import it.
@tool
def lookup_user(query: str) -> dict:
    """Look up a TechCorp employee by user id (E-4101) or by name. Returns the record or a typed miss. Use this before you reset a password."""
    row = _find_user(query)
    if not row:
        return {"found": False, "reason": f"unknown user {query}"}
    return _public_user(row)


# BREAK 1: delete the docstring line under def lookup_user and run. The decorator refuses with
# ValueError: Function must have a docstring if description not provided. Put it back and run.

# %%
# What a model is handed when these tools are bound: the name, the description and the parameters.
for t in (lookup_user, reset_password):
    print("name", t.name)
    print("description", t.description)
    print("handed_to_the_model", json.dumps(convert_to_openai_tool(t)["function"]["parameters"]))

# %%
# A tool is called through its own door, .invoke, which checks the arguments against the schema.
print("hit", lookup_user.invoke({"query": "E-4101"}))
print("miss", lookup_user.invoke({"query": "E-0000"}))

# BREAK 2: change {"query": "E-4101"} above to {"user": "E-4101"} and run. The schema refuses the call
# with a validation error that names query. Change it back to query and run.
