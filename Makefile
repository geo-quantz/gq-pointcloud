FIXTURE ?=

.PHONY: harness harness-update-baseline

# Run regression harness against all fixtures (or a specific one).
# Usage:
#   make harness
#   make harness FIXTURE=autzen-small
harness:
	@uv run python -m tests.harness.runner $(if $(FIXTURE),--fixture $(FIXTURE),)

# Update baselines to current metrics.
# IMPORTANT: commit baseline changes in a SEPARATE commit from impl changes.
# Usage:
#   make harness-update-baseline
#   make harness-update-baseline FIXTURE=autzen-small
harness-update-baseline:
	@uv run python -m tests.harness.runner --update-baseline $(if $(FIXTURE),--fixture $(FIXTURE),)
