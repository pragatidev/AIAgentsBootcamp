---
name: refund-policy
description: "Use when a DataFlow ticket asks for a refund, a return or money back on an order; not for billing questions or order status"
allowed-tools:
  - lookup_order
  - retrieve
  - decline_refund
---

Read the refunds ledger before you write. Decline when a refund row already exists. Cite the policy line from references/policy_lines.md. Never write without the confirm gate.

This Skill describes the procedure. It does not perform the write. The window number lives in the reference. Do not guess it.
