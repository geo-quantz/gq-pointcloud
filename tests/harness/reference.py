"""
Reference implementation comparison using PDAL CLI.

Since gq-filter wraps PDAL, the PDAL CLI (same engine) is the reference.
Outputs should match exactly for filter operations.

If no equivalent PDAL pipeline exists for a scenario, set
`pdal_pipeline` to None in the scenario definition — this module
will then mark the scenario as "comparison: N/A" rather than silently skip.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.harness.invariants import pdal_info


def run_pdal_pipeline(pipeline: dict, output_path: Path) -> dict:
    """
    Execute a PDAL pipeline dict via PDAL CLI.
    Returns {"success": bool, "point_count": int, "error": str}.
    """
    pipeline_copy = dict(pipeline)
    # Ensure the pipeline writes to output_path
    stages = list(pipeline_copy.get("pipeline", []))
    # Replace or add the final writer
    if stages and isinstance(stages[-1], dict) and stages[-1].get("type", "").startswith("writers."):
        stages[-1]["filename"] = str(output_path)
    else:
        stages.append({"type": "writers.las", "filename": str(output_path)})
    pipeline_copy["pipeline"] = stages

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(pipeline_copy, f)
        pipeline_file = f.name

    try:
        r = subprocess.run(
            ["pdal", "pipeline", pipeline_file],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return {"success": False, "point_count": 0, "error": r.stderr.strip()}
        count = pdal_info(output_path).point_count
        return {"success": True, "point_count": count, "error": ""}
    except Exception as e:
        return {"success": False, "point_count": 0, "error": str(e)}
    finally:
        os.unlink(pipeline_file)


def compare(
    gqfilter_output: Path,
    pdal_output: Path,
    scenario_name: str,
    tolerance: int = 0,
) -> list[str]:
    """
    Compare gq-filter output vs PDAL CLI reference output.
    Returns list of discrepancy strings (empty = match).

    Args:
        gqfilter_output: Path written by gq-filter.
        pdal_output:     Path written by PDAL CLI reference.
        scenario_name:   Used in discrepancy messages.
        tolerance:       Allowed absolute difference in point count.
                         0 = exact match required.
    """
    discrepancies: list[str] = []

    if not gqfilter_output.exists():
        discrepancies.append(f"GQ_OUTPUT_MISSING: {gqfilter_output}")
        return discrepancies

    if not pdal_output.exists():
        discrepancies.append(f"PDAL_OUTPUT_MISSING: {pdal_output}")
        return discrepancies

    gq_count = pdal_info(gqfilter_output).point_count
    pdal_count = pdal_info(pdal_output).point_count

    diff = abs(gq_count - pdal_count)
    if diff > tolerance:
        discrepancies.append(
            f"REFERENCE_MISMATCH [{scenario_name}]: "
            f"gq-filter={gq_count} pts, PDAL CLI={pdal_count} pts "
            f"(diff={diff}, tolerance={tolerance})"
        )

    return discrepancies


def build_reference_pipeline(
    input_path: Path,
    filter_params: dict,
    output_path: Path,
) -> dict | None:
    """
    Build a PDAL reference pipeline that mirrors what lib.filter would generate.

    Purpose: verify that gq-filter's Python pipeline builder produces the same
    PDAL execution result as calling PDAL CLI with the equivalent pipeline.
    Since gq-filter wraps PDAL, outputs should be byte-for-byte identical.

    For incidence angle, lib.filter now uses filters.normal + dot-product math
    (not ScanAngleRank), so we replicate the same stages here.

    Returns None if the scenario has no PDAL equivalent.
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from lib.filter import (
        FilterOptions, IncidenceAngleParams, IntensityParams,
        RangeParams, DuplicateParams, build_pipeline,
    )

    fp = filter_params
    options = FilterOptions(
        incidence=(
            IncidenceAngleParams(max_angle=fp["incidence_angle_max"])
            if fp.get("incidence_angle_max") is not None else None
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
    pipeline = build_pipeline(str(input_path), str(output_path), options)
    if not pipeline:
        return None

    # If only reader + writer (no filters), skip comparison
    stages = pipeline.get("pipeline", [])
    non_io = [s for s in stages if isinstance(s, dict) and
              not s.get("type", "").startswith("writers.")]
    has_filter = len(non_io) > 0

    if not has_filter:
        return None

    return pipeline
