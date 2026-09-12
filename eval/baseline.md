unique_tickets: 21
date: 2026-09-12
commit: 60cdbed

overall
faithfulness 0.762
context_recall 1.000
refused_correctly 1.000
fluent_misses 0
latency_s 13.50

per_kind
policy faithfulness 0.900 n=10
policy context_recall 1.000
policy refused_correctly 0.000
policy fluent_misses 0
lookup faithfulness 0.000 n=4
lookup context_recall 1.000
lookup refused_correctly 0.000
lookup fluent_misses 0
refuse faithfulness 1.000 n=5
refuse context_recall 1.000
refuse refused_correctly 1.000
refuse fluent_misses 0
park faithfulness 1.000 n=2
park context_recall 1.000
park refused_correctly 0.000
park fluent_misses 0

per_row
policy-return kind=policy faith=1 recall=1 refuse=0 route=retrieve
policy-shipping kind=policy faith=1 recall=1 refuse=0 route=retrieve
policy-billing kind=policy faith=1 recall=1 refuse=0 route=retrieve
policy-refund kind=policy faith=1 recall=1 refuse=0 route=retrieve
lookup-1001 kind=lookup faith=0 recall=1 refuse=0 route=lookup
lookup-1002 kind=lookup faith=0 recall=1 refuse=0 route=lookup
refuse-student kind=refuse faith=1 recall=1 refuse=1 route=retrieve
refuse-coffee kind=refuse faith=1 recall=1 refuse=1 route=retrieve
refuse-gym kind=refuse faith=1 recall=1 refuse=1 route=retrieve
policy-lamp kind=policy faith=0 recall=1 refuse=0 route=retrieve
policy-p0 kind=policy faith=1 recall=1 refuse=0 route=retrieve
policy-ship-in-country kind=policy faith=1 recall=1 refuse=0 route=retrieve
lookup-1003 kind=lookup faith=0 recall=1 refuse=0 route=lookup
lookup-1006 kind=lookup faith=0 recall=1 refuse=0 route=lookup
refuse-lounge kind=refuse faith=1 recall=1 refuse=1 route=retrieve
park-refund-1001 kind=park faith=1 recall=1 refuse=0 route=refund
park-refund-1005 kind=park faith=1 recall=1 refuse=0 route=refund
policy-live-chat kind=policy faith=1 recall=1 refuse=0 route=retrieve
policy-sso kind=policy faith=1 recall=1 refuse=0 route=retrieve
policy-2fa kind=policy faith=1 recall=1 refuse=0 route=retrieve
refuse-injection-escalate kind=refuse faith=1 recall=1 refuse=1.0 route=refuse
