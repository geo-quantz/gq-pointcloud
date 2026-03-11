import json
import os
import csv
import subprocess
import math
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List

import pdal
import numpy as np
import pye57

# -------------------------------
# 1. Parameter Definitions
# -------------------------------

@dataclass
class IncidenceAngleParams:
    min_angle: float # 面に対する最小角度 (例: 4度)
    max_angle: float # 面に対する最大角度 (例: 86度)
    enabled: bool = True

@dataclass
class RangeParams:
    max_distance: float
    enabled: bool = True

@dataclass
class VoxelParams:
    cell_size: float
    enabled: bool = True

@dataclass
class FilterOptions:
    preset_name: str
    incidence: Optional[IncidenceAngleParams] = None
    range_dist: Optional[RangeParams] = None
    voxel: Optional[VoxelParams] = None
    color_clean: bool = False
    color_threshold: float = 120.0
    ortho_path: Optional[str] = None
    deduplicate: bool = False
    report_enabled: bool = True

# -------------------------------
# 2. Pipeline Builders (Phase 1 & 2)
# -------------------------------

def get_origin_from_e57_header(path: str) -> Optional[Tuple[float, float, float]]:
    try:
        e57 = pye57.E57(path)
        if e57.scan_count > 0:
            pos = e57.get_header(0).translation
            return (float(pos[0]), float(pos[1]), float(pos[2]))
        e57.close()
    except: pass
    return None

def build_individual_pipeline(input_path: str, output_path: str, opt: FilterOptions) -> Dict[str, Any]:
    stages = []
    tag = "reader"
    stages.append({"type": "readers.e57", "filename": input_path, "tag": tag}) #
    
    origin = get_origin_from_e57_header(input_path)
    
    # 1. Range (15m制限)
    if opt.range_dist and origin:
        x0, y0, z0 = origin
        dx, dy, dz = f"(X-({x0}))", f"(Y-({y0}))", f"(Z-({z0}))"
        dist_sq = f"({dx}*{dx} + {dy}*{dy} + {dz}*{dz})"
        stages.append({
            "type": "filters.expression", #
            "expression": f"{dist_sq} <= {opt.range_dist.max_distance * opt.range_dist.max_distance}",
            "inputs": [tag], "tag": "range"
        })
        tag = "range"

    # 2. Incidence Angle (4-86度)
    if opt.incidence and origin:
        x0, y0, z0 = origin
        dx, dy, dz = f"(X-({x0}))", f"(Y-({y0}))", f"(Z-({z0}))"
        dot_expr = f"({dx}*NormalX + {dy}*NormalY + {dz}*NormalZ)" #
        v_len_sq = f"({dx}*{dx} + {dy}*{dy} + {dz}*{dz})"
        n_len_sq = f"(NormalX*NormalX + NormalY*NormalY + NormalZ*NormalZ)"
        cos_sq = f"(({dot_expr}*{dot_expr}) / ({v_len_sq} * {n_len_sq}))"
        
        # 面に対する角α=4〜86度は、法線との角θ=4〜86度と同じ範囲
        min_limit = math.cos(math.radians(opt.incidence.max_angle))**2
        max_limit = math.cos(math.radians(opt.incidence.min_angle))**2
        
        stages.append({
            "type": "filters.expression",
            "expression": f"{cos_sq} >= {min_limit} && {cos_sq} <= {max_limit}",
            "inputs": [tag], "tag": "inc"
        })
        tag = "inc"

    # 3. Voxel (1cm密度)
    if opt.voxel:
        stages.append({
            "type": "filters.voxelcentroidnearestneighbor", #
            "cell": opt.voxel.cell_size, 
            "inputs": [tag], "tag": "vox"
        })
        tag = "vox"

    stages.append({"type": "writers.las", "filename": output_path, "inputs": [tag]}) #
    return {"pipeline": stages}

def build_merge_pipeline(temp_files: List[str], output_path: str, opt: FilterOptions) -> Dict[str, Any]:
    stages = []
    input_tags = []
    for i, f in enumerate(temp_files):
        tag = f"tmp_{i}"
        stages.append({"type": "readers.las", "filename": f, "tag": tag})
        input_tags.append(tag)
    
    stages.append({"type": "filters.merge", "inputs": input_tags, "tag": "merged"})
    current = "merged"

    if opt.color_clean and opt.ortho_path and os.path.exists(opt.ortho_path):
        stages.append({
            "type": "filters.colorization",
            "raster": opt.ortho_path,
            "dimensions": "OrthoRed:1:1, OrthoGreen:1:2, OrthoBlue:1:3"
        })
        th = opt.color_threshold
        expr = f"(abs(Red/256.0 - OrthoRed) < {th}) && (abs(Green/256.0 - OrthoGreen) < {th}) && (abs(Blue/256.0 - OrthoBlue) < {th})"
        stages.append({"type": "filters.expression", "expression": expr, "tag": "color"})
        current = "color"

    stages.append({"type": "writers.las", "filename": output_path, "inputs": [current], "forward": "all"})
    return {"pipeline": stages}

def execute_pipeline(pipeline_dict: Dict[str, Any]) -> int:
    try:
        pl = pdal.Pipeline(json.dumps(pipeline_dict))
        pc = pl.execute()
        return pc
    except Exception as e:
        print(f"   PDAL Error: {e}")
        return 0

def save_report(output_dir: str, file_name: str, opt: FilterOptions, total_pts: int):
    report_path = os.path.join(output_dir, "processing_report.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = (
        f"[{timestamp}] Product: {file_name} | Preset: {opt.preset_name} | Points: {total_pts} | "
        f"Settings: Range={opt.range_dist.max_distance}m, Inc={opt.incidence.min_angle}-{opt.incidence.max_angle}deg, "
        f"Voxel={opt.voxel.cell_size}m, ColorClean={opt.color_clean}\n"
    )
    with open(report_path, "a", encoding="utf-8") as f:
        f.write(content)