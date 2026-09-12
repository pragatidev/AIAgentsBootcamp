"""Coding 6A solution."""

from dataflow.tools.orders import lookup_order_by_id


def lookup_or_miss(order_id: str) -> dict:
    return lookup_order_by_id(order_id)
