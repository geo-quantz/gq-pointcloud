import json
import os
import platform
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Union

# -------------------------------
# Windows DLL Resolution
# -------------------------------
if platform.system() == "Windows":
    # If PDAL_LIBRARY_PATH is set, add it to the DLL search path.
    # This is required for Python 3.8+ to find PDAL C++ DLLs.
    pdal_dll_path = os.environ.get("PDAL_LIBRARY_PATH")
    if pdal_dll_path and os.path.exists(pdal_dll_path):
        os.add_dll_directory(pdal_dll_path)

import pdal


# -------------------------------
# Parameter definitions
# -------------------------------

class FilterType:
    EXPRESSION = "filters.expression"
    UNIQUE = "filters.unique"
    DUPLICATE = "filters.duplicate"
    VOXEL = "filters.voxelcentroidnearestneighbor"
    COLORIZATION = "filters.colorization"
    MERGE = "filters.merge"


@dataclass
class IncidenceAngleParams:
    """Parameters for incidence angle filter.
    Many datasets approximate incidence using the LAS 'ScanAngleRank' dimension.
    """
    min_angle: float = 0.0
    max_angle: float = 90.0
    enabled: bool = True


@dataclass
class IntensityParams:
    """Parameters for intensity (return intensity) filter."""
    min_intensity: Optional[float] = None
    max_intensity: Optional[float] = None
    enabled: bool = True


@dataclass
class RangeParams:
    """Parameters for measurement distance (range) filter.
    For structured E57 files, we can automatically extract the scanner origin.
    For other formats (LAS), manual_origin should be provided or it defaults to (0,0,0).
    """
    min_distance: Optional[float] = None
    max_distance: Optional[float] = None
    manual_origin: Optional[Tuple[float, float, float]] = None
    enabled: bool = True


@dataclass
class VoxelParams:
    """Parameters for voxel-based downsampling."""
    cell_size: float
    enabled: bool = True


@dataclass
class ColorCleanParams:
    """Parameters for cleaning points based on color/intensity.
    If ortho_path is provided, colors are sampled and compared.
    """
    enabled: bool = True
    ortho_path: Optional[str] = None
    threshold: float = 70.0


@dataclass
class DuplicateParams:
    """Parameters for duplicate point filter.
    Uses PDAL's 'filters.unique,' which removes duplicate points (same XYZ).
    """
    enabled: bool = True


@dataclass
class FilterOptions:
    """Container for all filter parameters, used by the pipeline builder."""
    incidence: Optional[IncidenceAngleParams] = None
    intensity: Optional[IntensityParams] = None
    range_dist: Optional[RangeParams] = None
    voxel: Optional[VoxelParams] = None
    color_clean: Optional[ColorCleanParams] = None
    duplicate: Optional[DuplicateParams] = None
    preset_name: Optional[str] = None


# -------------------------------
# Utilities
# -------------------------------

def get_origin_auto(path: str) -> Optional[Tuple[float, float, float]]:
    """Attempt to extract scanner origin from E57 metadata using pdal info."""
    if not path.lower().endswith(".e57"):
        return None
    try:
        result = subprocess.run(['pdal', 'info', '--summary', path], capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        bounds = info.get("summary", {}).get("bounds", {})
        if bounds:
            return ((bounds['minx'] + bounds['maxx']) / 2,
                    (bounds['miny'] + bounds['maxy']) / 2,
                    (bounds['minz'] + bounds['maxz']) / 2)
    except:
        pass
    return None


def save_report(output_dir: str, filename: str, opt: FilterOptions, points: int):
    """Save a processing report to the output directory."""
    report_path = os.path.join(output_dir, "processing_report.txt")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format settings for the report
    settings = []
    if opt.range_dist:
        settings.append(f"Range={opt.range_dist.min_distance}-{opt.range_dist.max_distance}m")
    if opt.incidence:
        settings.append(f"Inc={opt.incidence.min_angle}-{opt.incidence.max_angle}deg")
    if opt.voxel:
        settings.append(f"Voxel={opt.voxel.cell_size}m")
    if opt.color_clean:
        settings.append(f"ColorClean={opt.color_clean.enabled}")
    
    line = f"[{now}] Product: {filename} | Preset: {opt.preset_name or 'custom'} | Points: {points} | Settings: {', '.join(settings)}\n"
    
    with open(report_path, "a", encoding="utf-8") as f:
        f.write(line)


# -------------------------------
# Filter builders (composable, data-driven)
# -------------------------------

def build_incidence_angle_filter(
        params: Optional[IncidenceAngleParams],
) -> Optional[Dict[str, Any]]:
    if not params or not params.enabled:
        return None
    
    expr = f"abs(ScanAngleRank) <= {params.max_angle}"
    if params.min_angle > 0:
        expr = f"abs(ScanAngleRank) >= {params.min_angle} && {expr}"
        
    return {
        "type": FilterType.EXPRESSION,
        "expression": expr,
    }


def build_intensity_filter(
        params: Optional[IntensityParams],
) -> Optional[Dict[str, Any]]:
    if not params or not params.enabled:
        return None

    expressions = []
    if params.min_intensity is not None:
        expressions.append(f"Intensity >= {params.min_intensity}")
    if params.max_intensity is not None:
        expressions.append(f"Intensity <= {params.max_intensity}")

    if not expressions:
        return None

    return {"type": FilterType.EXPRESSION, "expression": " && ".join(expressions)}


def build_range_filter(params: Optional[RangeParams], input_path: str) -> Optional[Dict[str, Any]]:
    if not params or not params.enabled:
        return None

    # Determine origin (0,0,0) by default, or auto-detect for E57
    origin = params.manual_origin
    if origin is None:
        origin = get_origin_auto(input_path) or (0.0, 0.0, 0.0)

    x0, y0, z0 = origin
    dist_expr = f"sqrt((X - {x0})**2 + (Y - {y0})**2 + (Z - {z0})**2)"
    
    conds = []
    if params.min_distance is not None:
        conds.append(f"{dist_expr} >= {params.min_distance}")
    if params.max_distance is not None:
        conds.append(f"{dist_expr} <= {params.max_distance}")

    if not conds:
        return None

    return {"type": FilterType.EXPRESSION, "expression": " && ".join(conds)}


def build_voxel_filter(params: Optional[VoxelParams]) -> Optional[Dict[str, Any]]:
    if not params or not params.enabled:
        return None
    return {"type": FilterType.VOXEL, "cell": params.cell_size}


def build_color_cleaning_stages(params: Optional[ColorCleanParams]) -> List[Dict[str, Any]]:
    if not params or not params.enabled:
        return []

    stages = []
    if params.ortho_path and os.path.exists(params.ortho_path):
        # Sample colors from ortho image
        stages.append({
            "type": FilterType.COLORIZATION,
            "raster": params.ortho_path,
            "dimensions": "OrthoRed:1:1, OrthoGreen:1:2, OrthoBlue:1:3"
        })
        # Remove points where color differs significantly from ortho
        expr = (f"(abs(Red - OrthoRed) < {params.threshold}) && "
                f"(abs(Green - OrthoGreen) < {params.threshold}) && "
                f"(abs(Blue - OrthoBlue) < {params.threshold})")
        stages.append({"type": FilterType.EXPRESSION, "expression": expr})
    else:
        # Fallback: simple brightness cleaning if no ortho provided
        stages.append({"type": FilterType.EXPRESSION, "expression": "(Red + Green + Blue) / 3 < 180"})
    
    return stages


def build_duplicate_filter(
        params: Optional[DuplicateParams],
) -> Optional[Dict[str, Any]]:
    if not params or not params.enabled:
        return None
    return {"type": FilterType.UNIQUE, "keep_first": True}


# -------------------------------
# Pipeline assembly & execution
# -------------------------------

def build_pipeline(
        input_paths: Union[str, List[str]], output_path: str, filter_params: FilterOptions, merge: bool = False
) -> Dict[str, Any]:
    """Assemble a PDAL pipeline dictionary from enabled filters.
    Supports single or multiple input files.
    """
    if isinstance(input_paths, str):
        input_paths = [input_paths]
    
    stages = []
    for p in input_paths:
        stages.append(p)
    
    if merge or len(input_paths) > 1:
        stages.append({"type": FilterType.MERGE})

    # Ordered list of filters
    # 1. Range (based on scanner origin) - Only applied to first file if not merging individual steps
    # Note: For multiple files, if they have different origins, they should be filtered individually first.
    # But for a single-pass merge pipeline, we apply what we can.
    f_range = build_range_filter(filter_params.range_dist, input_paths[0])
    if f_range: stages.append(f_range)

    # 2. Incidence Angle
    f_inc = build_incidence_angle_filter(filter_params.incidence)
    if f_inc: stages.append(f_inc)

    # 3. Intensity
    f_int = build_intensity_filter(filter_params.intensity)
    if f_int: stages.append(f_int)

    # 4. Color Cleaning
    stages.extend(build_color_cleaning_stages(filter_params.color_clean))

    # 5. Voxel Downsampling
    f_vox = build_voxel_filter(filter_params.voxel)
    if f_vox: stages.append(f_vox)

    # 6. Duplicate Removal
    f_dup = build_duplicate_filter(filter_params.duplicate)
    if f_dup: stages.append(f_dup)

    # Writer selection
    ext_out = os.path.splitext(output_path)[1].lower()
    writer_type = "writers.las"
    if ext_out == ".e57":
        writer_type = "writers.e57"
    elif output_path.endswith(".copc.laz"):
        writer_type = "writers.copc"
    elif ext_out in [".txt", ".csv"]:
        writer_type = "writers.text"

    stages.append({"type": writer_type, "filename": output_path})

    return {"pipeline": stages}


def execute_pipeline(pipeline_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a PDAL pipeline from a Python dictionary."""
    def _run(pdict: Dict[str, Any]) -> Dict[str, Any]:
        pl = pdal.Pipeline(json.dumps(pdict))
        pc = pl.execute()
        raw_md = pl.metadata
        md = json.loads(raw_md) if isinstance(raw_md, str) else raw_md
        return {
            "success": True,
            "points_processed": pc,
            "metadata": md,
            "log": pl.log,
        }

    try:
        return _run(pipeline_dict)
    except Exception as e:
        msg = str(e)
        if FilterType.UNIQUE in msg or "filters.duplicate" in msg:
            stages = [
                s
                for s in pipeline_dict.get("pipeline", [])
                if not (isinstance(s, dict) and s.get("type") in {FilterType.UNIQUE, "filters.duplicate"})
            ]
            try:
                result = _run({"pipeline": stages})
                result["note"] = "Duplicate filter unavailable; executed without it."
                return result
            except Exception as e2:
                return {"success": False, "error": str(e2), "log": ""}
        return {"success": False, "error": msg, "log": ""}
