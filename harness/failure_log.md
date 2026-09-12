# Failure log

## T-3005 double refund

ticket: T-3005
what happened: the desk issued 1 refund row(s) on DF-1010 with no guide in the window
bucket: missing_guide
why: nothing in the window said a refund already issued on this order must not be issued again
closed by:

## lookalike claimed refund on a miss

ticket: T-LOOKALIKE-DF-9999
what happened: the run reads like a model limit; lookup_found=False issued=False
bucket: missing_sensor
why: nothing compared the tool result to the reply before it reached the customer
closed by:
