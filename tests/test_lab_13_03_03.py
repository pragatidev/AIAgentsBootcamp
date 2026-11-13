"""Lab 13_03_03 (Lecture 29.3), build_auth typed by the student: the token, its issuer and its audience.

No model is called. Tokens come from a test key pair made in memory; the server runs on a free local port.
"""

import json
import runpy
from pathlib import Path

import pytest

from dataflow.mcp.auth import ISSUER, build_auth as package_build_auth, stand_in_keys
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_03_03_token_audience.py"
AUDIENCE_LINE = "        audience=audience,\n"


@pytest.fixture
def run_lab(capsys):
    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    return run


def _shape(provider) -> dict:
    verifier = provider.token_verifier
    return {
        "issuer": verifier.issuer,
        "audience": verifier.audience,
        "authorization_servers": [str(s) for s in provider.authorization_servers],
        "base_url": str(provider.base_url),
    }


def test_no_token_gets_401_and_a_metadata_pointer_that_resolves(run_lab):
    lab, out = run_lab()
    assert "no_token status 401" in out
    url = lab["url"]
    assert f'no_token www-authenticate Bearer resource_metadata="{lab["base_url"]}/.well-known/oauth-protected-resource/mcp"' in out
    assert "metadata status 200" in out
    text = "\n".join(out)
    document = json.loads(text[text.index("metadata {") + len("metadata ") : text.index("other_service_token")])
    assert document["resource"] == url
    assert document["authorization_servers"] == [ISSUER]


def test_the_other_service_token_is_refused_and_ours_is_served(run_lab):
    _, out = run_lab()
    assert any(line.startswith("server_log Bearer token rejected for client agent-desk: audience mismatch (got 'https://billing.dataflow.test/mcp'") for line in out)
    assert "other_service refused MCPError Server returned an error response" in out
    assert "this_server tools ['lookup_order', 'refund']" in out
    lookup = next(line for line in out if line.startswith("this_server lookup "))
    assert json.loads(lookup.split(" ", 2)[2])["item"] == "desk lamp"
    assert not any(line.startswith("other_service tools") for line in out)
    assert "server_stopped True" in out


def test_the_claims_name_issuer_audience_subject_and_scope(run_lab):
    lab, out = run_lab()
    other = json.loads(next(line for line in out if line.startswith("other_service_token ")).split(" ", 1)[1])
    ours = json.loads(next(line for line in out if line.startswith("this_server_token ")).split(" ", 1)[1])
    assert other["aud"] == "https://billing.dataflow.test/mcp" and ours["aud"] == lab["url"]
    for token in (other, ours):
        assert token["iss"] == ISSUER and token["sub"] == "agent-desk" and token["scope"] == "orders:read"
        assert 3500 < token["expires_in_s"] <= 3600


def test_lab_build_auth_matches_the_package(run_lab):
    lab, _ = run_lab()
    keys = stand_in_keys()
    args = (keys.public_key, ISSUER, "http://127.0.0.1:9/mcp", "http://127.0.0.1:9")
    assert _shape(lab["build_auth"](*args)) == _shape(package_build_auth(*args))


def test_without_the_audience_check_another_services_token_opens_the_server(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, AUDIENCE_LINE, "")
    _, out = run_lab(copy)
    assert "other_service tools ['lookup_order', 'refund']" in out
    assert any(line.startswith("other_service lookup ") for line in out)
    assert not any("audience mismatch" in line for line in out)
