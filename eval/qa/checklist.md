# DataFlow QA checklist

Every tick is a file path. An empty path is the find, not a pass.

| check | file path | status |
| --- | --- | --- |
| golden set | eval/golden.jsonl | pass |
| node tests | tests/test_nodes_dataflow.py | pass |
| eval CI | scripts/eval_ci.py | pass |
| fluent-miss cases | eval/runners/rag_metrics.py | pass |
| traces | dataflow/ops/tracer.py | pass |
| stop conditions | dataflow/graphs/durable.py | pass |
| load numbers | eval/load/replay.py | pass |
| UI paths | eval/ui/test_dataflow_chat.py | pass |
| parked write | eval/ui/test_dataflow_chat.py | pass |
