# DataFlow cost model

Four lines per ticket. Tokens and minutes. No return line.

| line | measured | source |
| --- | --- | --- |
| tokens by route | last ops/cost_report.md rows: 2292 tokens (thin request) and 6807 tokens (stuffed request). eval/load/replay.py prints tokens_per_ticket after a load run. | ops/cost_report.md, eval/load/replay.py |
| retries | retry spans live on the tracer. No committed retry rate is in this repo yet, so this line names the source instead of guessing a multiplier. | dataflow/ops/tracer.py |
| evals | 21 unique tickets in eval/baseline.md. latency_s 13.50 on that run. The golden runner is the eval cost. | eval/baseline.md, eval/runners/golden.py |
| human minutes | park rate 2 of 21 golden rows times the minutes a reviewer spends on one inbox card. Minutes-per-card is the buyer's number; this page does not invent it. | eval/golden.jsonl, dataflow/ambient/inbox.py |

The envelope is those four lines per ticket. The service already has a budget cap and a rate limit; the envelope is what those caps are set from.

There is no return on this page.
