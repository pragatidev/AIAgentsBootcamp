"""10.1 golden set shape and faithfulness runner. No Ollama required."""

from eval.runners.faithfulness import claims_of, supported_by_chunks
from eval.runners.golden import GOLDEN, load_golden, unique_tickets
from tests.fixtures.fake_model import FakeChatModel


def test_golden_file_has_twenty_distinct_rows():
    rows = load_golden(GOLDEN)
    assert len(rows) >= 20
    refuse_rows = [row for row in rows if row.get("kind") == "refuse"]
    assert len(refuse_rows) >= 4
    assert unique_tickets(rows) == len(rows)
    kinds = {str(row.get("kind") or "") for row in rows}
    assert kinds == {"policy", "lookup", "refuse", "park"}
    for row in rows:
        assert "id" in row
        assert "kind" in row
        assert "input" in row
        assert "reference" in row
        assert "tags" in row


def test_faithfulness_claims_split():
    claims = claims_of(
        "The customer return window is 30 days from delivery. "
        "Shipping is five business days inside the country."
    )
    assert len(claims) >= 2
    assert any("30 days" in claim for claim in claims)
    assert any("five business days" in claim for claim in claims)


def test_supported_by_chunks_with_fixture():
    chunks = [
        {
            "source": "dataflow/wiki/return_policy.md",
            "text": "The customer return window is 30 days from delivery.",
        }
    ]
    yes_model = FakeChatModel(reply="YES")
    no_model = FakeChatModel(reply="NO")
    assert supported_by_chunks(
        "The return window is 30 days.",
        chunks,
        model=yes_model,
    )
    assert not supported_by_chunks(
        "The refund window is 90 days.",
        chunks,
        model=no_model,
    )
