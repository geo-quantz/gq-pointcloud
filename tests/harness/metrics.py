"""
Metrics collection: point counts, processing time, peak memory.

Design notes (from spec):
- Processing time and memory vary by environment. Thresholds are set loose
  and relaxed further on non-Mac hardware.
- Environment is recorded alongside every metric snapshot so comparisons
  stay apples-to-apples.
"""
from __future__ import annotations

import platform
import resource
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any

from tests.harness.invariants import pdal_info


def _env_tag() -> str:
    """Short tag identifying the execution environment."""
    machine = platform.machine()  # arm64 / x86_64
    node = platform.node().split(".")[0]  # hostname prefix
    return f"{platform.system().lower()}-{machine}-{node}"


@dataclass
class RunMetrics:
    """All metrics captured for one scenario run."""
    fixture: str
    scenario: str

    # Point counts
    point_count_in: int = 0
    point_count_out: int = 0
    removal_rate: float = 0.0   # (in - out) / in

    # Performance (environment-dependent — compare only same env_tag)
    elapsed_sec: float = 0.0
    peak_memory_mb: float = 0.0
    env_tag: str = field(default_factory=_env_tag)

    # Optional accuracy metric against ground truth
    # For gq-filter (a filter, not a classifier) this is not applicable
    # unless a scenario specifically computes a class-preservation metric.
    accuracy_note: str = ""

    def as_dict(self) -> dict:
        return {
            "point_count_in": self.point_count_in,
            "point_count_out": self.point_count_out,
            "removal_rate": round(self.removal_rate, 6),
            "elapsed_sec": round(self.elapsed_sec, 4),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "env_tag": self.env_tag,
            "accuracy_note": self.accuracy_note,
        }


def measure(
    fn: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> tuple[Any, float, float]:
    """
    Call fn(*args, **kwargs), returning (result, elapsed_sec, peak_memory_mb).

    Uses wall-clock time and RSS memory via resource.getrusage for subprocess
    compatibility (tracemalloc only measures allocations within the Python
    process, not child processes spawned by pdal).
    """
    # Baseline memory before the call
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - t0

    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # ru_maxrss unit: bytes on Linux, bytes on macOS (actually kilobytes on
    # some systems). Normalise to MB.
    delta_bytes = max(0, after - before)
    # macOS returns bytes; Linux returns kilobytes.
    import sys
    if sys.platform == "darwin":
        peak_mb = delta_bytes / 1024 / 1024
    else:
        peak_mb = delta_bytes / 1024

    return result, elapsed, peak_mb


def collect(
    fixture_path: Path,
    output_path: Path,
    fixture_name: str,
    scenario_name: str,
    run_fn: Callable[[], Any],
) -> RunMetrics:
    """
    Run run_fn(), then measure elapsed time and peak memory.
    Reads point counts from fixture and output via PDAL CLI.
    """
    m = RunMetrics(fixture=fixture_name, scenario=scenario_name)

    in_info = pdal_info(fixture_path)
    m.point_count_in = in_info.point_count

    _, elapsed, peak_mb = measure(run_fn)
    m.elapsed_sec = elapsed
    m.peak_memory_mb = peak_mb

    if output_path.exists():
        out_info = pdal_info(output_path)
        m.point_count_out = out_info.point_count
        if m.point_count_in > 0:
            m.removal_rate = (
                (m.point_count_in - m.point_count_out) / m.point_count_in
            )

    return m
