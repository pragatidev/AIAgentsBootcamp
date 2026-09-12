# DataFlow agent spec

One page. Five fields. A team can staff it.

## Job

Answer DataFlow support tickets about orders and policy, and propose refunds for a reviewer. Anything not in that sentence is out of scope.

## Tools

Each tool is read or write. The list is the surface.

| tool | read or write |
| --- | --- |
| lookup_order | read |
| search_policy | read |
| issue_refund | write |
| decline_refund | write (typed miss, no ledger row) |

## Stop

Three lines.

1. The run ends when the reply is sent.
2. The run ends when the step or budget cap fires.
3. The run ends when the desk refuses because it has nothing.

## Gate

issue_refund waits. Lookups never wait. The named reviewer is reviewer-1 (allow list in harness/permissions.py). desk-lead resumes when reviewer-1 is not the actor. The actor id rides on every resume.

## Done-when

eval/golden.jsonl. Twenty-one unique tickets with references, including refusals and parks. The CI gate is scripts/eval_ci.py against eval/thresholds.toml. Done is that file, not a feeling.
