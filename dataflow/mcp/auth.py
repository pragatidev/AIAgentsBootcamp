"""The token check for the DataFlow orders server over HTTP (Lectures 29.1, 29.3, 29.4, 29.9).

The server is an OAuth 2.1 resource server: it reads a bearer token, checks it was signed by the
issuer it trusts and minted for this server (the audience), and serves its protected resource
metadata so a client can learn where tokens come from.

The labs mint their tokens with a test key pair that FastMCP ships, standing in for the company's
identity provider. In production the verifier reads the provider's published keys (jwks_uri=...)
and nothing else here changes.
"""

from __future__ import annotations

from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair

ISSUER = "https://auth.dataflow.test"


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


def stand_in_keys() -> RSAKeyPair:
    """A fresh RSA key pair in memory. The private half mints tokens; the server holds the public half."""
    return RSAKeyPair.generate()


def mint(keys: RSAKeyPair, *, audience: str, scopes: list[str], subject: str, issuer: str = ISSUER) -> str:
    """A signed token, as the identity provider would issue it, valid for one hour."""
    return keys.create_token(subject=subject, issuer=issuer, audience=audience, scopes=scopes)


def base_url_of(url: str) -> str:
    """http://127.0.0.1:8000/mcp -> http://127.0.0.1:8000, the server's own address."""
    return url.rsplit("/", 1)[0]
