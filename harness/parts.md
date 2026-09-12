# DataFlow harness parts

A map of the desk's harness. Each row names the file and the line that implements it. Empty rows are the next sections.

## Tools

- dataflow/tools/orders.py line 44 `lookup_order` (read)
- dataflow/tools/refund.py line 51 `issue_refund` (write)
- dataflow/tools/refund.py line 57 `decline_refund` (typed miss, no disk write)
- dataflow/agent/harness_loop.py runs those tools after the model proposes them

## Context policy

- AGENTS.md at the repo root (instruction map: role, scope, tool rules, refusal)
- config.py line 40 `def get_chat_model(` is the model chooser, not a policy file. The harness sits around it.

## Permissions

- none yet, Section 21

## Stop rules

- dataflow/agent/loop.py line 30 `max_steps` on the plain fixture loop
- dataflow/agent/harness_loop.py line 191 `max_steps` on the refund-path desk loop
- When the cap fires the desk prints STOPPED and the reason
