# %%
"""Lab 29.3: check the token and its audience.

What we build: the orders server as an OAuth resource server. You type build_auth: a verifier told which
issuer to trust and which audience a token must name, inside a provider that tells clients where their
tokens come from. Then you knock on the server with no token, with a token minted for another service,
and with a token minted for this server.

What you learn: over HTTP the server checks every request's bearer token before any tool runs: the
signature, the issuer, the expiry and the audience. The audience check is the one people forget. Without
it, a token your identity provider issued for a different service opens this one, which is why the
specification says a server MUST check that a token was minted for it. The lab mints its tokens with a
test key pair that FastMCP ships, as a stand-in for the company's identity provider; in production the
verifier reads the provider's published keys (a jwks_uri) and nothing else in this lab changes.

What will be true on your screen: the versions; with no token, status 401 and a WWW-Authenticate header
pointing at the server's metadata; that metadata document naming the authorization server; the claims of
two tokens; the token for another service refused, with the server's own "audience mismatch" line; the
token for this server listing the tools and looking up DF-1001.
"""

from pathlib import Path
from importlib.metadata import version
import json
import logging
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import httpx
import jwt
from fastmcp import Client
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier

from dataflow.mcp.auth import ISSUER, mint, stand_in_keys
from dataflow.mcp.http import build_http_server, free_port, start_http, url_for
from dataflow.mcp.runtime import run_async

print("mcp", version("mcp"), "fastmcp", version("fastmcp"), "PyJWT", version("PyJWT"))

# The verifier writes why it refused a token to its log. This prints those lines here, in plain text.
class ServerLog(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        print("server_log", record.getMessage())


logging.getLogger("fastmcp.server.auth.providers.jwt").addHandler(ServerLog())

# The stand-in identity provider: a key pair. The private half mints tokens, the server holds the public half.
keys = stand_in_keys()
port = free_port()
url = url_for(port)
base_url = f"http://127.0.0.1:{port}"


# %%
# TYPE THIS: build_auth. The signature and docstring are given; you type the body.
# Its finished copy is build_auth in dataflow/mcp/auth.py.
def build_auth(public_key: str, issuer: str, audience: str, base_url: str) -> RemoteAuthProvider:
    """Check every request's bearer token: signed by issuer's key, minted for audience, not expired."""
    verifier = JWTVerifier(
        public_key=public_key,
        issuer=issuer,
        audience=audience,
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[issuer],
        base_url=base_url,
    )


# BREAK: delete the line audience=audience, above and run. The token minted for the billing service is
# now accepted and lists this server's tools: a token taken from one service opens another. Put the line
# back and run.


# %%
# Start the server with your token check, and knock with no token.
url, stop = start_http(build_http_server(auth=build_auth(keys.public_key, ISSUER, url, base_url)), port)
print("url", url)
body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
reply = httpx.post(url, json=body, headers={"Accept": "application/json, text/event-stream"}, timeout=10)
print("no_token status", reply.status_code)
print("no_token www-authenticate", reply.headers.get("www-authenticate"))
metadata_url = reply.headers["www-authenticate"].split('resource_metadata="')[1].rstrip('"')
document = httpx.get(metadata_url, timeout=10)
print("metadata status", document.status_code)
print("metadata", json.dumps(document.json(), indent=2))


# %%
def claims(token: str) -> dict:
    """What a token says about itself. Reading it needs no key; trusting it needs the signature check."""
    raw = jwt.decode(token, options={"verify_signature": False})
    return {"iss": raw["iss"], "aud": raw["aud"], "sub": raw["sub"], "scope": raw.get("scope"), "expires_in_s": raw["exp"] - int(time.time())}


async def knock(label: str, token: str) -> None:
    """Connect with a token, list the tools, and look up one order."""
    try:
        async with Client(url, auth=token) as client:
            print(label, "tools", [tool.name for tool in await client.list_tools()])
            result = await client.call_tool("lookup_order", {"order_id": "DF-1001"})
            print(label, "lookup", json.dumps(result.data))
    except Exception as exc:
        print(label, "refused", type(exc).__name__, str(exc))


other = mint(keys, audience="https://billing.dataflow.test/mcp", scopes=["orders:read"], subject="agent-desk")
ours = mint(keys, audience=url, scopes=["orders:read"], subject="agent-desk")
print("other_service_token", json.dumps(claims(other)))
print("this_server_token", json.dumps(claims(ours)))
run_async(knock("other_service", other))
run_async(knock("this_server", ours))

# %%
print("server_stopped", stop())
