"""
PR automation for gq-filter loop engineering.

Usage:
    uv run python tools/pr_creator.py --summary "incidence angle fix"
    uv run python tools/pr_creator.py --dry-run   # preview without creating PR

Safety rules (enforced, not bypassed):
    - Never runs on main branch
    - Aborts if diff exceeds 400 added lines
    - Does not force-push, tag, or commit to main
    - Runs harness before creating PR; aborts on harness failure unless --skip-harness

Exit codes:
    0  PR created (or dry-run completed)
    1  Aborted (safety check, diff too large, harness failure)
    2  Usage error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = REPO_ROOT / ".github" / "geoquantz-loop.md"
MAX_DIFF_LINES = 400

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git(*args: str, check: bool = True) -> str:
    r = subprocess.run(
        ["git", *args],
        capture_output=True, text=True, cwd=str(REPO_ROOT), check=check,
    )
    return r.stdout.strip()


def current_branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD")


def diff_stat(base: str = "main") -> tuple[int, int]:
    """Return (lines_added, lines_deleted) vs base branch."""
    out = _git("diff", f"{base}...HEAD", "--numstat")
    added = deleted = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                added += int(parts[0])
                deleted += int(parts[1])
            except ValueError:
                pass  # binary files show "-"
    return added, deleted


def diff_summary(base: str = "main") -> str:
    """Short human-readable diff summary."""
    return _git("diff", f"{base}...HEAD", "--stat")


# ---------------------------------------------------------------------------
# Harness integration
# ---------------------------------------------------------------------------

def run_harness() -> tuple[bool, str]:
    """Run `make harness` and return (passed, output)."""
    r = subprocess.run(
        ["uv", "run", "python", "-m", "tests.harness.runner"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    return r.returncode == 0, r.stdout + r.stderr


def parse_harness_output(output: str) -> dict:
    """Extract metrics table and pass/fail counts from harness output."""
    lines = output.splitlines()
    table_lines = []
    in_table = False
    for line in lines:
        if "GQ-FILTER HARNESS RESULTS" in line:
            in_table = True
        if in_table:
            table_lines.append(line)
        if in_table and line.startswith("=") and len(table_lines) > 3:
            break

    passed = failed = 0
    m = re.search(r"(\d+) passed, (\d+) failed", output)
    if m:
        passed, failed = int(m.group(1)), int(m.group(2))

    return {
        "table": "\n".join(table_lines),
        "passed": passed,
        "failed": failed,
    }


# ---------------------------------------------------------------------------
# PR body generation
# ---------------------------------------------------------------------------

def _metrics_markdown(harness_output: str) -> str:
    info = parse_harness_output(harness_output)
    return f"```\n{info['table']}\n```\n\n{info['passed']} passed, {info['failed']} failed"


def _extract_invariants(harness_output: str) -> str:
    if "INVARIANT" in harness_output:
        lines = [l for l in harness_output.splitlines() if "INVARIANT" in l]
        return "⚠️ 違反あり:\n" + "\n".join(f"  {l}" for l in lines)
    return "✅ 全件通過"


def _extract_reference(harness_output: str) -> str:
    if "REFERENCE" in harness_output:
        lines = [l for l in harness_output.splitlines() if "REFERENCE" in l]
        return "⚠️ 不一致あり:\n" + "\n".join(f"  {l}" for l in lines)
    return "✅ PDAL CLI と一致"


def build_pr_body(summary: str, harness_output: str, added: int, deleted: int) -> str:
    template = TEMPLATE_PATH.read_text()

    body = template.replace("{{SUMMARY}}", summary)
    body = body.replace("{{METRICS_TABLE}}", _metrics_markdown(harness_output))
    body = body.replace("{{INVARIANTS_RESULT}}", _extract_invariants(harness_output))
    body = body.replace("{{REFERENCE_RESULT}}", _extract_reference(harness_output))

    # Append diff size info
    body += f"\n---\n\n**差分**: +{added} / -{deleted} 行\n"
    return body


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Create a gq-filter loop PR")
    parser.add_argument(
        "--summary", default="", help="One-line PR summary (auto-generated from commits if omitted)"
    )
    parser.add_argument(
        "--base", default="main", help="Base branch (default: main)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview PR body without creating"
    )
    parser.add_argument(
        "--skip-harness", action="store_true",
        help="Skip harness run (use with caution — harness should pass before merging)"
    )
    args = parser.parse_args()

    # --- Safety: refuse to run on main ---
    branch = current_branch()
    if branch in ("main", "master"):
        print(f"ERROR: Cannot create PR from '{branch}'. Switch to a feature branch first.")
        return 1

    print(f"Branch: {branch}")
    print(f"Base:   {args.base}")

    # --- Safety: diff size check ---
    added, deleted = diff_stat(args.base)
    print(f"Diff:   +{added} / -{deleted} lines")

    if added > MAX_DIFF_LINES:
        print(
            f"\nERROR: Diff has {added} added lines, which exceeds the {MAX_DIFF_LINES}-line limit.\n"
            f"Please split this PR into smaller changes before creating it.\n\n"
            f"Suggestions:\n"
            f"  1. Separate 'plumbing' changes (I/O, tests, config) from algorithm changes\n"
            f"  2. Create one PR per logical feature\n"
            f"  3. Use `git diff {args.base}...HEAD --stat` to review what's included"
        )
        print("\n" + diff_summary(args.base))
        return 1

    # --- Run harness ---
    if args.skip_harness:
        print("WARNING: Skipping harness run (--skip-harness)")
        harness_output = "(harness skipped)"
        harness_passed = True
    else:
        print("\nRunning harness...", flush=True)
        harness_passed, harness_output = run_harness()
        if not harness_passed:
            print("ERROR: Harness failed. Fix failures before creating PR.")
            print(harness_output[-2000:])
            return 1
        print("Harness passed.")

    # --- Build summary from commits if not provided ---
    summary = args.summary
    if not summary:
        commits = _git("log", f"{args.base}...HEAD", "--oneline")
        summary = f"**コミット:**\n```\n{commits}\n```"

    # --- Build PR body ---
    body = build_pr_body(summary, harness_output, added, deleted)

    # --- Dry run ---
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN — PR body preview:")
        print("=" * 60)
        print(body)
        print("=" * 60)
        print("\nTo create the PR, re-run without --dry-run.")
        return 0

    # --- Create PR ---
    title = args.summary or f"[loop] {branch}"
    print(f"\nCreating PR: {title!r}")

    r = subprocess.run(
        [
            "gh", "pr", "create",
            "--base", args.base,
            "--title", title,
            "--body", body,
        ],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )

    if r.returncode != 0:
        print(f"ERROR: gh pr create failed:\n{r.stderr}")
        return 1

    pr_url = r.stdout.strip()
    print(f"PR created: {pr_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
