# %%
"""Lab 28.6: a resource and a prompt on the DataFlow server.

What we build: the server's other two doors. The returns policy is already a fixed resource at
dataflow://policy/returns. You type a resource template, dataflow://wiki/{page}, that serves one help page
by name and refuses any name that lands outside the wiki folder, and the decline_refund prompt a reviewer
picks. Then a client lists both kinds, reads them, renders the prompt, and the application pins the
returns policy into the desk's system prompt.

What you learn: a tool is called by the model, a resource is read by the application, and a prompt is
picked by a person. A resource template turns part of an address into an argument, and an argument from a
client is input your server must check, like any tool argument. FastMCP screens template values for ".."
and absolute paths before your function runs; your own check is the one that knows where the wiki folder
is.

What will be true on your screen: the static resource, the template and the prompt as a client lists them;
the policy's first line and the shipping page read by address; an escaping name refused before your
function runs, and your check refusing the same name when the function is called directly; the decline
prompt rendered for DF-1001; and the start of a system prompt with the policy pinned into it.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from fastmcp import Client, FastMCP
from fastmcp.exceptions import ResourceError

from dataflow.mcp.bind import MCP_DESK_SYSTEM
from dataflow.mcp.runtime import run_async
from dataflow.mcp.server import WIKI_DIR

DECLINE_TEMPLATE = "We cannot refund order {order_id}. Reason: {reason}."
lab = FastMCP("dataflow-lab")


# A fixed resource: one address, one page. Its finished copy is returns_policy in dataflow/mcp/server.py.
@lab.resource("dataflow://policy/returns")
def returns_policy() -> str:
    """The DataFlow returns policy page."""
    return (WIKI_DIR / "return_policy.md").read_text(encoding="utf-8")


# %%
# TYPE THIS: wiki_page. The decorator, signature and docstring are given; you type the body.
# Its finished copy is wiki_page in dataflow/mcp/server.py.
@lab.resource("dataflow://wiki/{page}")
def wiki_page(page: str) -> str:
    """One DataFlow help page by file name, like return_policy.md. A name outside the wiki folder is refused."""
    path = (WIKI_DIR / page).resolve()
    if not path.is_relative_to(WIKI_DIR.resolve()) or not path.is_file():
        raise ResourceError(f"no wiki page named {page!r}")
    return path.read_text(encoding="utf-8")


# TYPE THIS: decline_refund. The decorator, signature and docstring are given; you type the body.
# Its finished copy is decline_refund in dataflow/mcp/server.py.
@lab.prompt
def decline_refund(order_id: str, reason: str) -> str:
    """A decline template for a refund reply."""
    return DECLINE_TEMPLATE.format(order_id=order_id, reason=reason)


# BREAK: delete the two lines of your check (the if and its raise) and run. Over MCP the escaping name is
# still refused, by FastMCP's own screen, before your function runs; but the direct call now reads
# config.py from the repo root, outside the wiki, and the missing page answers the client with the server's
# full file path. Your function is the last line of defence, and FastMCP is not the only way a value
# reaches it. To watch the escape over MCP too, also give the decorator
# security=None, which turns FastMCP's screen off for this template, and run. Put both back and run.

ESCAPE = "..%2F..%2Fconfig.py"


# %%
async def read(client: Client, uri: str) -> str:
    contents = await client.read_resource(uri)
    return contents[0].text


async def tour() -> str:
    async with Client(lab) as client:
        print("resources", [str(r.uri) for r in await client.list_resources()])
        print("templates", [t.uri_template for t in await client.list_resource_templates()])
        prompts = await client.list_prompts()
        print("prompts", [(p.name, [a.name for a in p.arguments or []]) for p in prompts])

        policy = await read(client, "dataflow://policy/returns")
        print("policy_first_line", policy.splitlines()[0])
        print("wiki shipping.md first_line", (await read(client, "dataflow://wiki/shipping.md")).splitlines()[0])
        # The server logs this refusal with a traceback on stderr: that is the server's log, not a crash.
        try:
            print("wiki missing.md", await read(client, "dataflow://wiki/missing.md"))
        except Exception as exc:
            print("wiki missing.md refused", type(exc).__name__, exc)
        try:
            text = await read(client, "dataflow://wiki/" + ESCAPE)
            print("wiki escape read", text.splitlines()[0])
        except Exception as exc:
            print("wiki escape refused", type(exc).__name__, exc)

        rendered = await client.get_prompt("decline_refund", {"order_id": "DF-1001", "reason": "outside the 30 day window"})
        print("prompt role", rendered.messages[0].role)
        print("prompt text", rendered.messages[0].content.text)
        return policy


policy = run_async(tour())

# FastMCP decodes %2F to "/" before it screens or calls you, so this is the value the function would get.
try:
    print("direct escape read", wiki_page("../../config.py").splitlines()[0])
except ResourceError as exc:
    print("direct escape refused", exc)

# %%
# The application decides what goes in front of the model: here it pins the policy into the system prompt.
system_prompt = MCP_DESK_SYSTEM + "\n\nThe DataFlow returns policy, read from dataflow://policy/returns:\n" + policy
print("system_prompt_chars", len(system_prompt))
for line in system_prompt.splitlines()[:4]:
    print("system_prompt |", line)
