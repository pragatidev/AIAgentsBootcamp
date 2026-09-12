# Calibration note

Human labels vs the judge on the same ten golden ids.
The judge did not write the labels file.

agreement: 7/10

| id | human label | judge label | agree |
| --- | --- | --- | --- |
| policy-return | grounded | grounded | yes |
| policy-shipping | grounded | grounded | yes |
| policy-billing | grounded | grounded | yes |
| policy-refund | grounded | grounded | yes |
| lookup-1001 | grounded | ungrounded | no |
| lookup-1002 | grounded | ungrounded | no |
| refuse-coffee | refuse | refuse | yes |
| refuse-gym | refuse | refuse | yes |
| policy-lamp | grounded | grounded | yes |
| park-refund-1001 | park | ungrounded | no |

## trust

- policy: trust alone
- lookup: never
- refuse: trust alone
- park: never

They mostly agree. Keep the note anyway: the disagreements are the licence, not the matching rows.
Trust the judge alone on policy and refuse; flag lookup and park for a human; never let it decide those kinds in CI.
