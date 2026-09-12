"""Computational control: the refund record has the required fields."""

from __future__ import annotations

REQUIRED = ("order_id", "amount", "reason")


class SchemaError(ValueError):
    """Raised with the field name so the message is a diagnosis."""

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__("schema_assert failed: missing or invalid field " + field)


def schema_assert(record) -> bool:
    """Raise SchemaError naming the field when the record is not a valid refund."""
    if not isinstance(record, dict):
        raise SchemaError("record")
    for field in REQUIRED:
        if field not in record or record[field] is None or record[field] == "":
            raise SchemaError(field)
    try:
        amount = float(record["amount"])
    except (TypeError, ValueError) as exc:
        raise SchemaError("amount") from exc
    if amount <= 0:
        raise SchemaError("amount")
    if not isinstance(record["order_id"], str) or not record["order_id"].strip():
        raise SchemaError("order_id")
    if not isinstance(record["reason"], str) or not record["reason"].strip():
        raise SchemaError("reason")
    return True
