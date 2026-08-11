"""
Harness runner — entry point for `make harness`.

Usage:
    python -m tests.harness.runner              # all fixtures
    python -m tests.harness.runner --fixture autzen-small
    python -m tests.harness.runner --update-baseline
    python -m tests.harness.runner --update-baseline --fixture autzen-small

Output contract:
    - Failures are printed prominently.
    - Passing scenarios are summarised in a single line.
    - Exit code 0 = all pass, 1 = at least one failure.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Resolve repo root
REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
BASELINES_DIR = REPO_ROOT / "tests" / "baselines"

sys.path.insert(0, str(REPO_ROOT))

from tests.harness.invariants import check_invariants, pdal_info
from tests.harness.metrics import collect, RunMetrics
from tests.harness import baseline, reference
from tests.harness.scenarios import SCENARIOS


# ---------------------------------------------------------------------------
# gq-filter execution
# ---------------------------------------------------------------------------

def _run_gqfilter(input_path: Path, output_path: Path, filter_params: dict) -> dict:
    """
    Execute gq-filter via its pipeline builder (lib/filter.py), then run the
    resulting pipeline dict via PDAL CLI.

    This approach tests lib.filter.build_pipeline() — the core library logic —
    without requiring PDAL Python bindings to be importable in the harness
    process (the bindings may be broken due to system library version mismatch).

    Returns {"success": bool, "error": str}.
    """
    # Import only the pure-Python parts of lib/filter (no pdal import triggered).
    from lib.filter import (
        FilterOptions,
        IncidenceAngleParams,
        IntensityParams,
        RangeParams,
        DuplicateParams,
        build_pipeline,
    )

    fp = filter_params
    options = FilterOptions(
        incidence=(
            IncidenceAngleParams(max_angle=fp["incidence_angle_max"])
            if fp.get("incidence_angle_max") is not None
            else None
        ),
        intensity=(
            IntensityParams(
                min_intensity=fp.get("intensity_min"),
                max_intensity=fp.get("intensity_max"),
            )
            if (fp.get("intensity_min") is not None or fp.get("intensity_max") is not None)
            else None
        ),
        range_dist=(
            RangeParams(
                min_distance=fp.get("range_min"),
                max_distance=fp.get("range_max"),
            )
            if (fp.get("range_min") is not None or fp.get("range_max") is not None)
            else None
        ),
        duplicate=(
            DuplicateParams(enabled=True) if fp.get("duplicate") else None
        ),
    )

    pipeline_dict = build_pipeline(str(input_path), str(output_path), options)

    # Execute the generated pipeline via PDAL CLI
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(pipeline_dict, f)
        pipeline_file = f.name

    try:
        r = subprocess.run(
            ["pdal", "pipeline", pipeline_file],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return {"success": False, "error": r.stderr.strip() or r.stdout.strip()}
        return {"success": True, "error": ""}
    finally:
        os.unlink(pipeline_file)


# ---------------------------------------------------------------------------
# Single scenario
# ---------------------------------------------------------------------------

def run_scenario(
    fixture_path: Path,
    scenario: dict,
    tmpdir: Path,
    update_baseline: bool,
) -> dict:
    """Run one scenario. Returns result dict with pass/fail and details."""
    name = scenario["name"]
    fixture_name = fixture_path.stem  # e.g. "autzen-small"
    fp = scenario["filter_params"]

    output_path = tmpdir / f"{fixture_name}_{name}_gqfilter.las"
    ref_output_path = tmpdir / f"{fixture_name}_{name}_pdal.las"

    result = {
        "fixture": fixture_name,
        "scenario": name,
        "description": scenario.get("description", ""),
        "passed": True,
        "failures": [],
    }

    # --- 1. Run gq-filter ---
    def _run():
        return _run_gqfilter(fixture_path, output_path, fp)

    from tests.harness.metrics import collect as metrics_collect
    metrics = metrics_collect(
        fixture_path, output_path,
        fixture_name, name,
        _run,
    )
    result["metrics"] = metrics.as_dict()

    if not output_path.exists():
        result["passed"] = False
        result["failures"].append(f"GQ_FILTER_FAILED: output not created")
        return result

    # --- 2. Invariant checks ---
    violations = check_invariants(fixture_path, output_path, operation="filter")
    if violations:
        result["passed"] = False
        result["failures"].extend([f"INVARIANT: {v}" for v in violations])

    # --- 3. Reference comparison ---
    ref_pipeline = reference.build_reference_pipeline(
        fixture_path, fp, ref_output_path
    )
    if ref_pipeline is None:
        result["reference"] = "N/A (no PDAL equivalent for this scenario)"
    else:
        ref_result = reference.run_pdal_pipeline(ref_pipeline, ref_output_path)
        if not ref_result["success"]:
            result["reference"] = f"PDAL_CLI_FAILED: {ref_result['error']}"
        else:
            discrepancies = reference.compare(output_path, ref_output_path, name)
            if discrepancies:
                result["passed"] = False
                result["failures"].extend([f"REFERENCE: {d}" for d in discrepancies])
                result["reference"] = "MISMATCH"
            else:
                result["reference"] = f"OK (PDAL CLI: {ref_result['point_count']} pts)"

    # --- 4. Baseline comparison ---
    metrics_dict = metrics.as_dict()
    regressions = baseline.compare(fixture_name, name, metrics_dict)
    if regressions:
        result["passed"] = False
        result["failures"].extend([f"BASELINE: {r}" for r in regressions])

    if update_baseline:
        baseline.save(fixture_name, name, metrics_dict)

    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _print_results(results: list[dict]) -> int:
    """Print harness results. Returns exit code (0 = all pass, 1 = failures)."""
    failures = [r for r in results if not r["passed"]]
    passes = [r for r in results if r["passed"]]

    print()
    print("=" * 62)
    print("  GQ-FILTER HARNESS RESULTS")
    print("=" * 62)

    for r in results:
        m = r.get("metrics", {})
        pts_in = m.get("point_count_in", "?")
        pts_out = m.get("point_count_out", "?")
        rate = m.get("removal_rate", 0.0)
        elapsed = m.get("elapsed_sec", 0.0)
        mem = m.get("peak_memory_mb", 0.0)
        ref = r.get("reference", "")

        status = "PASS" if r["passed"] else "FAIL"
        label = f"[{status}]"

        line = (
            f"  {label:<6} {r['fixture']}/{r['scenario']:<22}"
            f" {pts_out:>6} pts  −{rate:.1%}  {elapsed:.2f}s  {mem:.0f}MB"
        )
        print(line)

        if not r["passed"]:
            for f in r.get("failures", []):
                print(f"         ↳ {f}")

        if ref and not ref.startswith("OK"):
            print(f"         ref: {ref}")

    print("-" * 62)
    print(f"  {len(passes)} passed, {len(failures)} failed")
    print("=" * 62)
    print()

    return 0 if not failures else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="GeoQuantz regression harness"
    )
    parser.add_argument(
        "--fixture",
        help="Run only this fixture (stem name, e.g. autzen-small)",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help=(
            "Save current metrics as the new baseline. "
            "IMPORTANT: commit baseline changes in a separate commit "
            "from implementation changes."
        ),
    )
    args = parser.parse_args()

    # Discover fixtures
    fixture_paths = sorted(FIXTURES_DIR.glob("*.laz")) + sorted(
        FIXTURES_DIR.glob("*.las")
    )
    # Exclude non-data files (the manifest is .md)
    if args.fixture:
        fixture_paths = [p for p in fixture_paths if p.stem == args.fixture]
        if not fixture_paths:
            print(f"ERROR: fixture '{args.fixture}' not found in {FIXTURES_DIR}")
            return 1

    if not fixture_paths:
        print(f"No fixtures found in {FIXTURES_DIR}. Run `git lfs pull` first.")
        return 1

    if args.update_baseline:
        print("⚠️  --update-baseline mode: metrics will be saved as new baselines.")
        print("   Commit baseline changes separately from implementation changes.")
        print()

    results = []
    with tempfile.TemporaryDirectory(prefix="gq-harness-") as tmpdir:
        for fixture_path in fixture_paths:
            print(f"▶ Fixture: {fixture_path.name}", flush=True)
            in_info = pdal_info(fixture_path)
            print(f"  {in_info.point_count} points", flush=True)

            for scenario in SCENARIOS:
                sys.stdout.write(
                    f"  · {scenario['name']:<24} ... "
                )
                sys.stdout.flush()
                r = run_scenario(
                    fixture_path,
                    scenario,
                    Path(tmpdir),
                    args.update_baseline,
                )
                results.append(r)
                status = "✓" if r["passed"] else "✗"
                m = r.get("metrics", {})
                print(
                    f"{status}  {m.get('point_count_out', '?')} pts  "
                    f"{m.get('elapsed_sec', 0):.2f}s"
                )

    return _print_results(results)


if __name__ == "__main__":
    sys.exit(main())
