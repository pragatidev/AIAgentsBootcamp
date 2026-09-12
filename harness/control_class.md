# Control class

Measured on a planted refund record with the amount missing.

| class | check | what it caught | cost |
| computational | schema_assert | field amount (schema_assert failed: missing or invalid field amount) | 0.009 ms, 0 tokens |
| inferential | policy_judge | verdict PASS | 13522.791 ms, 557 tokens |

Rule: schema and allowlist first. Judge only where a computer cannot decide.
