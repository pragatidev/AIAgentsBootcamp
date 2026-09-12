# DataFlow price from cost

Inputs named from career/pm/cost_model.md. Hours and seats. A margin as a percentage of cost. No forecast of the buyer's side of the ledger.

## Per ticket (scales with volume)

- tokens by route (cost model line 1: ops/cost_report.md, eval/load/replay.py)
- retries (cost model line 2: dataflow/ops/tracer.py)
- eval tokens for the golden run that measures the desk (cost model line 3: eval/baseline.md)
- reviewer minutes (cost model line 4: park rate times minutes per inbox card)

## Per month (does not scale with one extra ticket)

- operator hours: inbox watch, golden-row edits, Monday trace read
- seats: local Ollama host, local tracer jsonl. No extra product seat on the student default.

## Stated margin

20 percent of the token-and-hours cost. Written on its own line so it can be lowered without hiding the cost underneath. Not a promise.

## Doubling test

eval/baseline.md unique_tickets is 21. Double that to 42.

The token line doubles. Reviewer minutes double with parks (2 of 21 becomes 4 of 42). Operator hours for the Monday trace stay. If a monthly hours number stays flat while parks double, the page no longer covers the desk.
