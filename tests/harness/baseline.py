"""
Baseline management.

Rules (from spec):
- Expected values are stored in JSON files tracked by Git.
- Baseline updates must be INDEPENDENT commits — never mixed with impl changes.
- On update, show a human-readable diff of what changed.
- The initial baseline requires human review before being treated as ground truth.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASELINE_DIR = Path(__file__).parent.parent / "baselines"

# Thresholds for performance metrics.
# These are intentionally LOOSE to avoid false positives from environment noise.
# The spec says: "If you tighten these, loops will stop on false positives."
_PERF_TOLERANCE = {
    "elapsed_sec": 5.0,       # allowed absolute increase in seconds
    "peak_memory_mb": 256.0,  # allowed absolute increase in MB
}


def load(fixture_name: str, scenario: str) -> dict | None:
    """Load baseline for a fixture+scenario. Returns None if none saved yet."""
    path = _path(fixture_name)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get(scenario)


def save(fixture_name: str, scenario: str, metrics: dict) -> None:
    """
    Save (or update) baseline for a fixture+scenario.
    Prints a human-readable diff when overwriting an existing value.
    """
    path = _path(fixture_name)
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if path.exists():
        existing = json.loads(path.read_text())

    old = existing.get(scenario)
    existing[scenario] = metrics

    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n")

    if old is not None:
        diff = _diff(old, metrics)
        if diff:
            print(f"\n[baseline updated] {fixture_name} / {scenario}")
            for line in diff:
                print(f"  {line}")
        else:
            print(f"[baseline unchanged] {fixture_name} / {scenario}")
    else:
        print(f"[baseline created]  {fixture_name} / {scenario}")


def compare(
    fixture_name: str,
    scenario: str,
    actual: dict,
) -> list[str]:
    """
    Compare actual metrics against the stored baseline.
    Returns a list of regression messages (empty = no regression).

    Point count is compared exactly.
    Performance metrics use loose absolute tolerances.
    """
    expected = load(fixture_name, scenario)
    if expected is None:
        return []  # No baseline yet — first run, nothing to compare

    regressions: list[str] = []

    # Exact check: point count must not change
    if "point_count_out" in expected and "point_count_out" in actual:
        if actual["point_count_out"] != expected["point_count_out"]:
            regressions.append(
                f"POINT_COUNT_DRIFT: expected {expected['point_count_out']}, "
                f"got {actual['point_count_out']}"
            )

    if "removal_rate" in expected and "removal_rate" in actual:
        delta = abs(actual["removal_rate"] - expected["removal_rate"])
        if delta > 1e-4:
            regressions.append(
                f"REMOVAL_RATE_DRIFT: expected {expected['removal_rate']:.4%}, "
                f"got {actual['removal_rate']:.4%} (Δ={delta:.4%})"
            )

    # Loose check: performance (only flag significant regressions)
    for key, tol in _PERF_TOLERANCE.items():
        if key in expected and key in actual:
            delta = actual[key] - expected[key]
            if delta > tol:
                regressions.append(
                    f"PERF_REGRESSION {key}: expected ≤{expected[key]:.3f}, "
                    f"got {actual[key]:.3f} (+{delta:.3f}, threshold {tol})"
                )

    return regressions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _path(fixture_name: str) -> Path:
    return BASELINE_DIR / f"{fixture_name}.json"


def _diff(old: dict, new: dict) -> list[str]:
    lines = []
    all_keys = sorted(set(old) | set(new))
    for k in all_keys:
        if k not in old:
            lines.append(f"+ {k}: {new[k]}")
        elif k not in new:
            lines.append(f"- {k}: (removed)")
        elif old[k] != new[k]:
            lines.append(f"  {k}: {old[k]} → {new[k]}")
    return lines
