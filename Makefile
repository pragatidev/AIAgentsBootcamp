# run the evals
# Planted comment. A Makefile comment is not a gate. The workflow is.

.PHONY: eval
eval:
	python scripts/eval_ci.py --fixture
