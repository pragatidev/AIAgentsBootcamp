# DataFlow one-job offer

A page a buyer can say no to. Nothing on this page about the buyer's ledger.

| row | entry |
| --- | --- |
| job | Answer DataFlow support tickets about orders and policy, and propose refunds for a reviewer. |
| service level | Task success by kind as eval/baseline.md (policy 0.900, lookup 0.000, refuse 1.000, park 1.000). Refuse rate 1.000 on should-refuse rows. Park rate 2 of 21 unique tickets. Tokens per ticket from career/pm/cost_model.md. Measured at the load eval/load/replay.py tests. |
| gate | issue_refund parks. Named reviewer: reviewer-1. desk-lead above that line. The inbox is dataflow/ambient/inbox.py. |
| contract | A refusal is correct behaviour. When retrieval is empty the desk says so, and the golden set scores that as right, not as a defect. |

What it does not do: it does not replace a support team, it does not invent a policy, it does not write a refund without reviewer-1, and it does not run as a chatbot with no gate.
