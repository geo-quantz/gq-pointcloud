FIXTURE ?=
SUMMARY ?=

.PHONY: harness harness-update-baseline pr pr-dry-run

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

# Create a PR for the current feature branch.
# Runs harness, checks diff size (<= 400 lines), then calls gh pr create.
# Usage:
#   make pr SUMMARY="fix: incidence angle edge case"
#   make pr-dry-run SUMMARY="..."   # preview without creating
pr:
	@uv run python tools/pr_creator.py $(if $(SUMMARY),--summary "$(SUMMARY)",)

pr-dry-run:
	@uv run python tools/pr_creator.py --dry-run $(if $(SUMMARY),--summary "$(SUMMARY)",)
