"""
Evaluation script for the 7 new filters added in PR #6-#12.
Tests each filter against tests/fixtures/autzen-small.laz (7,388 pts, ft units).

Usage:
    python tools/evaluate_new_filters.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "autzen-small.laz"
IN_PTS = 7388

# autzen-small coordinate ranges (Oregon State Plane, feet)
X_MIN, X_MAX = 636500.07, 636620.0
Y_MIN, Y_MAX = 851700.03, 851820.0
Z_MIN, Z_MAX = 424.76, 498.26


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pdal_run(pipeline: dict) -> tuple[int, float, str]:
    """Execute a PDAL pipeline JSON, return (point_count, elapsed_sec, error)."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir="/tmp"
    ) as f:
        json.dump(pipeline, f)
        pfile = f.name

    out_path = None
    for stage in pipeline["pipeline"]:
        if isinstance(stage, dict) and "filename" in stage:
            out_path = stage["filename"]

    t0 = time.perf_counter()
    r = subprocess.run(
        ["pdal", "pipeline", pfile],
        capture_output=True, text=True,
    )
    elapsed = time.perf_counter() - t0
    os.unlink(pfile)

    if r.returncode != 0:
        return 0, elapsed, (r.stderr.strip() or r.stdout.strip())[:200]

    if out_path and os.path.exists(out_path):
        info_r = subprocess.run(
            ["pdal", "info", "--summary", out_path],
            capture_output=True, text=True,
        )
        if info_r.returncode == 0:
            data = json.loads(info_r.stdout)
            pts = data.get("summary", {}).get("num_points", 0)
            return pts, elapsed, ""

    return 0, elapsed, "output not found"


def check_classification(output: str, expected_classes: set) -> str:
    """Verify that only the expected classification codes appear in output."""
    r = subprocess.run(
        ["pdal", "info", "--stats", "--filters.stats.dimensions=Classification",
         output],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return f"pdal info failed: {r.stderr[:100]}"
    data = json.loads(r.stdout)
    # collect all distinct values from histogram
    stats = data.get("stats", {}).get("statistic", [])
    for s in stats:
        if s.get("name") == "Classification":
            histogram = s.get("histogram", {})
            # histogram is a list of {value, count}
            actual_classes = set()
            for entry in histogram:
                if entry.get("count", 0) > 0:
                    actual_classes.add(int(entry.get("value", -1)))
            unexpected = actual_classes - expected_classes
            if unexpected:
                return f"UNEXPECTED classes: {unexpected}"
            return f"OK — classes present: {sorted(actual_classes)}"
    return "Classification stats not found"


def run_test(name: str, pipeline: dict, tmpdir: Path, notes: str = "",
             verify_fn=None) -> dict:
    out_path = tmpdir / f"{name}.las"
    # patch output filename into writer stage
    for stage in pipeline["pipeline"]:
        if isinstance(stage, dict) and stage.get("type", "").startswith("writers."):
            stage["filename"] = str(out_path)
            break

    pts, elapsed, err = pdal_run(pipeline)
    rate = (IN_PTS - pts) / IN_PTS if pts > 0 else 1.0
    status = "PASS" if not err and pts > 0 else "FAIL"

    extra = ""
    if not err and pts > 0 and verify_fn:
        extra = verify_fn(str(out_path))

    return {
        "name": name,
        "status": status,
        "pts_in": IN_PTS,
        "pts_out": pts,
        "removal_rate": rate,
        "elapsed_sec": elapsed,
        "error": err,
        "notes": notes,
        "verify": extra,
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def build_tests(tmpdir: Path) -> list[dict]:
    fixture = str(FIXTURE)

    tests = []

    # ------------------------------------------------------------------
    # 1. Statistical Outlier Removal (filters.outlier statistical)
    # ------------------------------------------------------------------
    tests.append(run_test("01_statistical_outlier_default", {
        "pipeline": [
            fixture,
            {"type": "filters.outlier", "method": "statistical", "mean_k": 8, "multiplier": 2.0},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="k=8, 2σ (default params)"))

    tests.append(run_test("01b_statistical_outlier_strict", {
        "pipeline": [
            fixture,
            {"type": "filters.outlier", "method": "statistical", "mean_k": 16, "multiplier": 1.5},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="k=16, 1.5σ (strict)"))

    # ------------------------------------------------------------------
    # 2. Radius Outlier Removal (filters.outlier radius)
    # ------------------------------------------------------------------
    tests.append(run_test("02_radius_outlier_default", {
        "pipeline": [
            fixture,
            {"type": "filters.outlier", "method": "radius", "radius": 1.0, "min_k": 2},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="radius=1.0ft, min_k=2 (default)"))

    tests.append(run_test("02b_radius_outlier_tight", {
        "pipeline": [
            fixture,
            {"type": "filters.outlier", "method": "radius", "radius": 0.5, "min_k": 5},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="radius=0.5ft, min_k=5 (tight — expect more removal)"))

    # ------------------------------------------------------------------
    # 3. Classification Code Filter
    # Ground truth: autzen has classes 0, 2, 5, 6
    # ------------------------------------------------------------------
    out_cls = tmpdir / "03_cls_ground.las"
    tests.append(run_test("03_cls_ground_only", {
        "pipeline": [
            fixture,
            {"type": "filters.expression", "expression": "(Classification == 2)"},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="Keep Classification=2 (Ground) only",
    verify_fn=lambda p: check_classification(p, {2})))

    tests.append(run_test("03b_cls_ground_building", {
        "pipeline": [
            fixture,
            {"type": "filters.expression",
             "expression": "(Classification == 2 || Classification == 6)"},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="Keep Ground(2) + Building(6)",
    verify_fn=lambda p: check_classification(p, {2, 6})))

    # ------------------------------------------------------------------
    # 4. Return Number Filter
    # ------------------------------------------------------------------
    tests.append(run_test("04_first_return_only", {
        "pipeline": [
            fixture,
            {"type": "filters.expression", "expression": "(ReturnNumber == 1)"},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="Keep ReturnNumber=1 (first returns) only"))

    tests.append(run_test("04b_first_and_second_return", {
        "pipeline": [
            fixture,
            {"type": "filters.expression",
             "expression": "(ReturnNumber == 1 || ReturnNumber == 2)"},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="Keep first + second returns"))

    # ------------------------------------------------------------------
    # 5. Spatial Clip (filters.crop)
    # Clip to inner half of XY extent
    # ------------------------------------------------------------------
    x_c = (X_MIN + X_MAX) / 2
    y_c = (Y_MIN + Y_MAX) / 2
    tests.append(run_test("05_spatial_clip_xy", {
        "pipeline": [
            fixture,
            {"type": "filters.crop",
             "bounds": f"([{X_MIN},{x_c}],[{Y_MIN},{y_c}])"},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes=f"Clip to SW quadrant (X:{X_MIN:.0f}-{x_c:.0f}, Y:{Y_MIN:.0f}-{y_c:.0f})"))

    tests.append(run_test("05b_spatial_clip_xyz", {
        "pipeline": [
            fixture,
            {"type": "filters.crop",
             "bounds": f"([{X_MIN},{X_MAX}],[{Y_MIN},{Y_MAX}],[{Z_MIN},{460.0}])"},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes=f"Clip Z <= 460ft (low-elevation ground)"))

    # ------------------------------------------------------------------
    # 6. Height (Z) Filter — filters.expression on Z
    # ------------------------------------------------------------------
    tests.append(run_test("06_z_min_only", {
        "pipeline": [
            fixture,
            {"type": "filters.expression", "expression": f"Z >= {Z_MIN + 20}"},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes=f"Remove low elevation (Z < {Z_MIN+20:.1f}ft)"))

    tests.append(run_test("06b_z_range", {
        "pipeline": [
            fixture,
            {"type": "filters.expression",
             "expression": f"Z >= {Z_MIN} && Z <= {(Z_MIN+Z_MAX)/2}"},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes=f"Keep Z {Z_MIN:.1f}–{(Z_MIN+Z_MAX)/2:.1f}ft (lower half)"))

    # ------------------------------------------------------------------
    # 7. Radius-based Thinning (filters.sample)
    # ------------------------------------------------------------------
    tests.append(run_test("07_radius_sample_small", {
        "pipeline": [
            fixture,
            {"type": "filters.sample", "radius": 0.5},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="Poisson disk, radius=0.5ft (~15cm)"))

    tests.append(run_test("07b_radius_sample_large", {
        "pipeline": [
            fixture,
            {"type": "filters.sample", "radius": 2.0},
            {"type": "writers.las", "filename": "__REPLACE__"},
        ]
    }, tmpdir, notes="Poisson disk, radius=2.0ft (~60cm) — aggressive thinning"))

    return tests


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(results: list[dict]) -> int:
    print()
    print("=" * 78)
    print("  GQ-FILTER NEW FEATURES EVALUATION — autzen-small.laz (7,388 pts)")
    print("=" * 78)
    print(f"  {'Filter':<36} {'Out':>6} {'Removed':>8}  {'Time':>6}  Status")
    print("-" * 78)

    failed = []
    for r in results:
        removal = f"-{r['removal_rate']:.1%}"
        time_s = f"{r['elapsed_sec']:.2f}s"
        status = f"[{r['status']}]"
        line = (
            f"  {r['name']:<36} {r['pts_out']:>6} {removal:>8}  {time_s:>6}  {status}"
        )
        print(line)
        if r["notes"]:
            print(f"    → {r['notes']}")
        if r["verify"]:
            print(f"    ✓ verify: {r['verify']}")
        if r["error"]:
            print(f"    ✗ ERROR: {r['error']}")
            failed.append(r["name"])

    print("-" * 78)
    pass_count = len(results) - len(failed)
    print(f"  {pass_count}/{len(results)} passed")
    print("=" * 78)
    print()
    return 0 if not failed else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not FIXTURE.exists():
        print(f"ERROR: fixture not found: {FIXTURE}")
        print("Run: git lfs pull")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="gq-eval-") as tmpdir:
        results = build_tests(Path(tmpdir))

    sys.exit(print_report(results))
