# %% [markdown]
# Write a typed tool with the tools decorator. TechCorp reset_password.
#
# When this works, the tool's name, description and args schema are
# printed, then a known id resets and an unknown id is a typed miss.
# The break is a tool with no docstring.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.tools import tool

from techcorp.tools.accounts import dummy_runtime, reset_password

print("name", reset_password.name)
print("description", reset_password.description)
print("args_schema", reset_password.args_schema)
print("args_schema_json", reset_password.tool_call_schema.model_json_schema())
print("args", reset_password.args)

# %%
known = reset_password.func("E-4101", runtime=dummy_runtime())
print("known", known)
unknown = reset_password.func("E-0000", runtime=dummy_runtime())
print("unknown", unknown)

# %%
print("BREAK: a tool with no docstring")
try:

    @tool
    def blank_reset(user_id: str) -> dict:
        return {"found": True, "user_id": user_id, "temporary_password": "nope"}

    print("blank_name", blank_reset.name)
    print("blank_description", repr(blank_reset.description))
except Exception as err:
    print("decorator_error_type", type(err).__name__)
    print("decorator_error", err)
