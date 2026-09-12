"""13.2 Skills: frontmatter, match, reference, the Skill path cannot write."""

from langchain_core.messages import AIMessage, HumanMessage

from dataflow.guardrails.allowlist import guard_tools
from dataflow.graphs.rag_tool_cycle import build_rag_tool_cycle
from dataflow.skills.loader import (
    load_body,
    load_reference,
    load_skills,
    match,
    parse_frontmatter,
)
from dataflow.tools.refund import issue_refund, read_refunds
from tests.fixtures.fake_model import FakeChatModel, FakeToolModel

REFUND_ASK = "Please refund order DF-1001, the lamp is unused"
BILLING_ASK = "How much is an extra user on Professional?"
SKILL_MD = (
    "---\n"
    "name: refund-policy\n"
    "description: Use when a DataFlow ticket asks for a refund\n"
    "allowed-tools:\n"
    "  - lookup_order\n"
    "  - retrieve\n"
    "  - decline_refund\n"
    "---\n"
    "\n"
    "Read the ledger.\n"
)


def test_frontmatter_parses():
    meta, body = parse_frontmatter(SKILL_MD)
    assert meta["name"] == "refund-policy"
    assert "refund" in str(meta["description"])
    assert meta["allowed-tools"] == ["lookup_order", "retrieve", "decline_refund"]
    assert "Read the ledger" in body


def test_match_loads_refund_and_skips_billing():
    skills = load_skills()
    assert skills
    assert skills[0]["name"] == "refund-policy"
    model = FakeChatModel()
    loaded = match(REFUND_ASK, skills, model=model)
    skipped = match(BILLING_ASK, skills, model=model)
    assert loaded is not None
    assert loaded["name"] == "refund-policy"
    assert skipped is None


def test_reference_loads():
    skills = load_skills()
    text = load_reference(skills[0], "policy_lines.md")
    assert "Source: dataflow/wiki/return_policy.md" in text
    assert "30 days from delivery" in text
    assert load_body(skills[0])
    assert "references/policy_lines.md" in load_body(skills[0])


def test_skill_path_cannot_write_when_port_is_on(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "refunds.jsonl"))
    tools = guard_tools([issue_refund], actor_id="anon")
    model = FakeToolModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "issue_refund",
                        "args": {
                            "order_id": "DF-1001",
                            "amount": 49.0,
                            "reason": "now",
                        },
                        "id": "call_refund",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="blocked at the port"),
        ]
    )
    skills = load_skills()
    system = load_body(skills[0])
    graph = build_rag_tool_cycle(model=model, tools=tools, system=system)
    graph.invoke({"messages": [HumanMessage(content=REFUND_ASK)]})
    assert read_refunds() == []
    assert not (tmp_path / "refunds.jsonl").exists()
