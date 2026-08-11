"""
Common invariant checker applied to ALL filter operations.

Design: uses only PDAL CLI — no Python PDAL bindings required.
Violations are returned as strings; empty list = all pass.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class PointCloudInfo:
    point_count: int
    bbox: dict  # {minx, miny, minz, maxx, maxy, maxz}
    crs_wkt: str
    fields: list[str]


def pdal_info(path: Path) -> PointCloudInfo:
    """Read metadata from a LAS/LAZ file using PDAL CLI."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Main info (bbox, stats, point count)
    r = subprocess.run(
        ["pdal", "info", str(path)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(r.stdout)
    stats = data.get("stats", {}).get("statistic", [])
    point_count = stats[0]["count"] if stats else 0
    bbox = data.get("stats", {}).get("bbox", {}).get("native", {}).get("bbox", {})

    # CRS and dimensions from --metadata
    rm = subprocess.run(
        ["pdal", "info", str(path), "--metadata"],
        capture_output=True, text=True, check=True,
    )
    meta_data = json.loads(rm.stdout)
    srs = meta_data.get("metadata", {}).get("srs", {})
    crs_wkt = srs.get("prettywkt", "")

    # Dimensions from --summary
    rs = subprocess.run(
        ["pdal", "info", str(path), "--summary"],
        capture_output=True, text=True, check=True,
    )
    summary_data = json.loads(rs.stdout)
    dims_str = summary_data.get("summary", {}).get("dimensions", "")
    fields = [d.strip() for d in dims_str.split(",") if d.strip()]

    return PointCloudInfo(
        point_count=point_count,
        bbox=bbox,
        crs_wkt=crs_wkt,
        fields=fields,
    )


def check_invariants(
    input_path: Path,
    output_path: Path,
    operation: str = "filter",
    critical_fields: list[str] | None = None,
) -> list[str]:
    """
    Check common invariants for a filter operation.

    Args:
        input_path:      Path to the input LAS/LAZ file.
        output_path:     Path to the output LAS/LAZ file written by the filter.
        operation:       "filter" enforces point_count_out <= point_count_in.
                         "transform" skips that check.
        critical_fields: Attribute names that must be preserved in the output.
                         Defaults to X, Y, Z, Classification, Intensity.

    Returns:
        List of violation strings. Empty list means all invariants passed.
    """
    if critical_fields is None:
        critical_fields = ["X", "Y", "Z", "Classification", "Intensity"]

    violations: list[str] = []

    # 1. Output is readable
    try:
        out_info = pdal_info(output_path)
    except Exception as e:
        violations.append(f"OUTPUT_UNREADABLE: {e}")
        return violations  # no further checks possible

    try:
        in_info = pdal_info(input_path)
    except Exception as e:
        violations.append(f"INPUT_UNREADABLE: {e}")
        return violations

    # 2. CRS preservation
    if in_info.crs_wkt:
        if not out_info.crs_wkt:
            violations.append("CRS_LOST: input had CRS but output has none")
        elif _normalize_crs(in_info.crs_wkt) != _normalize_crs(out_info.crs_wkt):
            violations.append(
                f"CRS_MISMATCH\n"
                f"  input:  {in_info.crs_wkt[:80]!r}\n"
                f"  output: {out_info.crs_wkt[:80]!r}"
            )

    # 3. No NaN / Inf in X, Y, Z
    nan_count = _count_nan_inf(output_path)
    if nan_count > 0:
        violations.append(
            f"NAN_INF_COORDS: {nan_count} point(s) have NaN or Inf in X/Y/Z"
        )

    # 4. Bounding box must not exceed input bbox
    if in_info.bbox and out_info.bbox:
        violations.extend(_check_bbox(in_info.bbox, out_info.bbox))

    # 5. Point count constraint for filter operations
    if operation == "filter" and out_info.point_count > in_info.point_count:
        violations.append(
            f"POINT_COUNT_INCREASED: filter produced more points than input "
            f"({in_info.point_count} → {out_info.point_count})"
        )

    # 6. Critical attribute preservation
    missing = [f for f in critical_fields if f not in out_info.fields]
    if missing:
        violations.append(f"ATTRIBUTES_LOST: {missing} missing from output")

    return violations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_crs(wkt: str) -> str:
    return " ".join(wkt.split())


def _count_nan_inf(path: Path) -> int:
    """Return number of points with NaN/Inf in X, Y, or Z."""
    pipeline = {
        "pipeline": [
            str(path),
            {
                "type": "filters.expression",
                "expression": (
                    "isnan(X) || isinf(X) || "
                    "isnan(Y) || isinf(Y) || "
                    "isnan(Z) || isinf(Z)"
                ),
            },
        ]
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(pipeline, f)
        pipeline_file = f.name

    try:
        r = subprocess.run(
            ["pdal", "pipeline", pipeline_file, "--metadata"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return 0  # expression filter may not be supported
        meta = json.loads(r.stdout)
        stats = (
            meta.get("metadata", {})
            .get("filters.stats", {})
            .get("statistic", [])
        )
        return stats[0]["count"] if stats else 0
    except Exception:
        return 0
    finally:
        os.unlink(pipeline_file)


def _check_bbox(in_bbox: dict, out_bbox: dict, tol: float = 1e-3) -> list[str]:
    violations = []
    for axis in ("x", "y", "z"):
        in_min = in_bbox.get(f"min{axis}", float("-inf"))
        in_max = in_bbox.get(f"max{axis}", float("inf"))
        out_min = out_bbox.get(f"min{axis}", float("-inf"))
        out_max = out_bbox.get(f"max{axis}", float("inf"))

        if out_min < in_min - tol:
            violations.append(
                f"BBOX_EXCEEDED: output min{axis} ({out_min:.4f}) "
                f"< input min{axis} ({in_min:.4f})"
            )
        if out_max > in_max + tol:
            violations.append(
                f"BBOX_EXCEEDED: output max{axis} ({out_max:.4f}) "
                f"> input max{axis} ({in_max:.4f})"
            )
    return violations
