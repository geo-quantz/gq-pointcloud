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
    Build a PDAL reference pipeline equivalent to the gq-filter scenario.

    filter_params keys:
      incidence_angle_max  (float | None)
      intensity_min        (float | None)
      intensity_max        (float | None)
      range_min            (float | None)
      range_max            (float | None)
      duplicate            (bool)

    Returns None if the scenario has no PDAL equivalent
    (caller should log "comparison: N/A").
    """
    stages: list = [str(input_path)]
    has_filter = False

    if (v := filter_params.get("incidence_angle_max")) is not None:
        stages.append({
            "type": "filters.expression",
            "expression": f"abs(ScanAngleRank) <= {v}",
        })
        has_filter = True

    intensity_parts = []
    if (v := filter_params.get("intensity_min")) is not None:
        intensity_parts.append(f"Intensity >= {v}")
    if (v := filter_params.get("intensity_max")) is not None:
        intensity_parts.append(f"Intensity <= {v}")
    if intensity_parts:
        stages.append({
            "type": "filters.expression",
            "expression": " && ".join(intensity_parts),
        })
        has_filter = True

    range_parts = []
    dist_expr = "sqrt(X*X + Y*Y + Z*Z)"
    if (v := filter_params.get("range_min")) is not None:
        range_parts.append(f"{dist_expr} >= {v}")
    if (v := filter_params.get("range_max")) is not None:
        range_parts.append(f"{dist_expr} <= {v}")
    if range_parts:
        stages.append({
            "type": "filters.expression",
            "expression": " && ".join(range_parts),
        })
        has_filter = True

    if filter_params.get("duplicate", False):
        stages.append({"type": "filters.label_duplicates"})
        stages.append({"type": "filters.expression", "expression": "Withheld == 0"})
        has_filter = True

    if not has_filter:
        return None

    stages.append({"type": "writers.las", "filename": str(output_path)})
    return {"pipeline": stages}
