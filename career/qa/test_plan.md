# DataFlow test plan

Five layers. QA owns the failure modes. Each row is a path a hire can open.

| layer | path | status |
| --- | --- | --- |
| node tests | tests/test_nodes_dataflow.py | proved (classify and refuse). lookup typed miss is tests/test_tools_orders.py. refund park is tests/test_dataflow_hitl.py. |
| golden set | eval/golden.jsonl | proved |
| load | eval/load/replay.py | proved |
| fluent miss | eval/runners/faithfulness.py | proved |
| UI check | eval/ui/test_dataflow_chat.py | proved |

The checklist that walks this table is eval/qa/checklist.md.

No row is still owed: every path exists in this repo. A chat screenshot is not coverage.
