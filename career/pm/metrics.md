# DataFlow metrics

Four numbers a stand-up can read. The PM owns the golden set.

| metric | number | source |
| --- | --- | --- |
| task success by kind | policy faithfulness 0.900 n=10; lookup 0.000 n=4; refuse 1.000 n=5; park 1.000 n=2 | eval/baseline.md |
| refuse rate | should-refuse refused_correctly 1.000; should-answer fluent_misses 0 on policy and on lookup | eval/baseline.md |
| park rate | 2 park rows of 21 unique tickets; read beside the inbox length | eval/golden.jsonl, dataflow/ambient/inbox.py |
| tokens per ticket by route | last service report lists 2292 tokens (thin) and 6807 tokens (stuffed); the load runner prints tokens_per_ticket after a run | ops/cost_report.md, eval/load/replay.py |

Notes.

Task success is per kind because a desk that is right on refuse and wrong on lookup has one problem, not a blended score.

Refuse rate is two numbers. A single refuse rate hides which is which.

Park rate is not good or bad on its own. A desk that parks every refund is doing the gate. A desk that parks lookups is misrouting. Read it next to dataflow/ambient/inbox.py.

Tokens are the metric. Money is one multiplication that changes with the model; this page does not do that multiplication.
