# DataFlow human-gate policy

Four rows. Reads run. Writes wait. A named owner resumes.

| row | policy |
| --- | --- |
| which tools park | issue_refund parks. lookup_order and search_policy do not. decline_refund does not, because it writes nothing. |
| who resumes and the line | reviewer-1 or reviewer-2 resume a parked refund. desk-lead resumes when those reviewers are not the actor, or when the card is edited. Nobody else. The allow list is harness/permissions.py. The actor id on the resume is how this row is audited. |
| oldest first, escalate after the window | The inbox sorts oldest first (dataflow/ambient/inbox.py). A park older than the review window is escalated to desk-lead, not approved by age. The window is the on-call SLA the desk lead sets. This page does not invent a minute count. |
| approve, reject, or edit | Approve. Reject with a reason. Edit the amount within the bound on the card (the order's charged amount). Anything else is a new ticket. |

What this policy refuses: parking a read; approving by age; resuming as a shared account.
