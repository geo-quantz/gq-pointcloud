import argparse
import json
import sys
import os
import glob
from datetime import datetime
from typing import List, Dict, Any, Tuple
import concurrent.futures

from lib.filter import (
    DuplicateParams,
    FilterOptions,
    IncidenceAngleParams,
    IntensityParams,
    RangeParams,
    VoxelParams,
    ColorCleanParams,
    ClassificationParams,
    build_pipeline,
    execute_pipeline,
    save_report,
)

# -------------------------------
# Preset Definitions
# -------------------------------
#PRESETS: Dict[str, Dict[str, Any]] = {
#    "tls": {
#        "incidence_angle_min": 0.0,
#        "incidence_angle_max": 86.0,  # 入射角制限: 地表面から4度以上を確保 (90度 - 4度 = 86度以内)
#        "range_min": 0.5,
#        "range_max": 15.0,            # 距離制限: 機器の最大測距距離の80%以内（例として15m制限）
#        "voxel_size": 0.01,           # 点密度: 10mmボクセル（グラウンドデータ・高密度用）
#    },
#        "tls2": {
#        "incidence_angle_min": 0.0,
#        "incidence_angle_max": 86.0,  # 入射角制限: 地表面から4度以上を確保 (90度 - 4度 = 86度以内)
#        "range_min": 0.3,
#        "range_max": 18.0,            # 距離制限: 機器の最大測距距離の80%以内（例として15m制限）
#        "voxel_size": 0.001,           # 点密度: 10mmボクセル（グラウンドデータ・高密度用）
#    },
#    "uav": {
#        "incidence_angle_min": 0.0,
#        "incidence_angle_max": 45.0,  # UAVスキャン角制限: 直下から45度以内を採用
#        "range_min": 2.0,
#        "range_max": 150.0,
#        "voxel_size": 0.05,           # 点密度: 50mmボクセル（地図情報レベル500の400点/m²相当）
#    }
#}

# -------------------------------
# Preset Definitions
# -------------------------------
def load_presets() -> Dict[str, Dict[str, Any]]:
    """外部ファイル(presets.json)からプリセットを読み込む。なければデフォルトを作成する。"""
    # 実行ファイル(.exe)やスクリプト(.py)がある場所のディレクトリを取得
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    preset_path = os.path.join(base_dir, "presets.json")
    
    # 組み込みのデフォルト設定
    default_presets = {
        "tls": {
            "incidence_angle_min": 0.0,
            "incidence_angle_max": 86.0,  # 掠射角4度確保
            "range_min": 0.5,
            "range_max": 15.0,            # 15m制限
            "voxel_size": 0.01,           # 10mmボクセル
        },
        "uav": {
            "incidence_angle_min": 0.0,
            "incidence_angle_max": 45.0,
            "range_min": 2.0,
            "range_max": 150.0,
            "voxel_size": 0.05,
        }
    }
    
    if os.path.exists(preset_path):
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] プリセットファイル({preset_path})の読み込みに失敗しました。組み込み設定を使用します: {e}")
            return default_presets
    else:
        # 初回起動時にデフォルトのプリセットファイルを自動生成
        try:
            with open(preset_path, "w", encoding="utf-8") as f:
                json.dump(default_presets, f, indent=4, ensure_ascii=False)
            print(f"[INFO] プリセット定義ファイルを自動作成しました: {preset_path}")
        except Exception as e:
            print(f"[WARNING] プリセットファイルの作成に失敗しました: {e}")
        return default_presets

# グローバル変数として読み込んだ辞書を保持（これ以降のコードは変更不要）
PRESETS = load_presets()


def parse_args(args: List[str]) -> argparse.Namespace:
    """Parses command-line arguments for the PDAL filter pipeline."""
    parser = argparse.ArgumentParser(
        description="GeoQuantz PointCloud Pipeline: 公共測量準拠の幾何学フィルタリングを一括処理するCLIツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # TLSデータの標準処理（15m制限、10mmボクセル、入射角4度カット）
  python main.py --preset tls
  
  # UAVデータの標準処理（150m制限、50mmボクセル、スキャン角45度カット）
  python main.py --preset uav
        """
    )

    # Core IO arguments
    parser.add_argument(
        "--input", "-i", default="01_raw", help="Path to the input file or directory (Default: 01_raw)."
    )
    parser.add_argument(
        "--output", "-o", default="04_product", help="Path to the output file or directory (Default: 04_product)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated PDAL pipeline dictionary without executing it.",
    )
    parser.add_argument(
        "--preset",
        choices=PRESETS.keys(),
        help="Use a predefined preset for TLS or UAV surveying standards.",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge all input files into a single output file (only if input is a directory).",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Process files individually (default for directory input unless --merge is set).",
    )

    # Incidence Angle Filter Group
    incidence_group = parser.add_argument_group("Incidence Angle Filter")
    incidence_group.add_argument(
        "--incidence-angle-min",
        type=float,
        help="Minimum scan angle (abs ScanAngleRank).",
    )
    incidence_group.add_argument(
        "--incidence-angle-max",
        "--iam",
        type=float,
        help="Maximum scan angle (abs ScanAngleRank).",
    )

    # Intensity Filter Group
    intensity_group = parser.add_argument_group("Intensity Filter")
    intensity_group.add_argument(
        "--intensity-min",
        "--imin",
        type=float,
        help="Minimum intensity value.",
    )
    intensity_group.add_argument(
        "--intensity-max",
        "--imax",
        type=float,
        help="Maximum intensity value.",
    )

    # Measurement Distance (Range) Filter Group
    range_group = parser.add_argument_group("Measurement Distance Filter")
    range_group.add_argument(
        "--range-min",
        "--rmin",
        type=float,
        help="Minimum Euclidean distance from origin.",
    )
    range_group.add_argument(
        "--range-max",
        "--rmax",
        type=float,
        help="Maximum Euclidean distance from origin.",
    )
    range_group.add_argument(
        "--origin",
        type=float,
        nargs=3,
        metavar=('X', 'Y', 'Z'),
        help="Manual scanner origin for distance filter (default: auto-detect or 0,0,0).",
    )

    # Voxel Filter Group
    voxel_group = parser.add_argument_group("Voxel Filter")
    voxel_group.add_argument(
        "--voxel-size",
        "--vs",
        type=float,
        help="Cell size for voxel centroid downsampling.",
    )

    # Color Cleaning Group
    color_group = parser.add_argument_group("Color Cleaning Filter")
    color_group.add_argument(
        "--color-clean",
        action="store_true",
        help="Enable color cleaning (fallback to brightness if no ortho-path).",
    )
    color_group.add_argument(
        "--ortho-path",
        type=str,
        help="Path to ortho image for color reference.",
    )
    color_group.add_argument(
        "--color-threshold",
        type=float,
        default=70.0,
        help="Color difference threshold (default: 70).",
    )

    # Duplicate Filter Group
    duplicate_group = parser.add_argument_group("Duplicate Filter")
    duplicate_group.add_argument(
        "--deduplicate",
        "-d",
        action="store_true",
        help="Enable duplicate point removal (removes exact XYZ matches).",
    )

    # Classification Filter Group
    cls_group = parser.add_argument_group("Classification Filter")
    cls_group.add_argument(
        "--keep-classes",
        type=int,
        nargs="+",
        metavar="CODE",
        help=(
            "Retain only points with these ASPRS classification codes. "
            "e.g. --keep-classes 2 6  (ground + buildings). "
            "Common codes: 2=Ground 3=LowVeg 4=MedVeg 5=HighVeg 6=Building "
            "7=Noise 9=Water 17=Bridge"
        ),
    )

    # Performance Group
    perf_group = parser.add_argument_group("Performance")
    perf_group.add_argument(
        "--max-workers",
        "-w",
        type=int,
        default=None,
        help="並列処理の最大数。指定しない場合は (CPUコア数 - 1) が自動設定されます。",
    )

    return parser.parse_args(args)


def assemble_config(args: argparse.Namespace) -> FilterOptions:
    """
    Maps CLI arguments to the structured FilterOptions configuration object.
    If a preset is selected, its values are used as defaults and can be overridden by explicit flags.
    """
    # Initialize with preset values if available
    p_values = PRESETS.get(args.preset, {}) if args.preset else {}

    # Helper to resolve value from args or preset
    def get_val(arg_name, preset_key=None):
        val = getattr(args, arg_name, None)
        if val is None and preset_key:
            return p_values.get(preset_key)
        return val

    # Incidence filter
    i_min = get_val("incidence_angle_min", "incidence_angle_min")
    i_max = get_val("incidence_angle_max", "incidence_angle_max")
    incidence = None
    if i_min is not None or i_max is not None:
        incidence = IncidenceAngleParams(
            min_angle=i_min if i_min is not None else 0.0,
            max_angle=i_max if i_max is not None else 90.0
        )

    # Intensity filter
    int_min = get_val("intensity_min", "intensity_min")
    int_max = get_val("intensity_max", "intensity_max")
    intensity = None
    if int_min is not None or int_max is not None:
        intensity = IntensityParams(min_intensity=int_min, max_intensity=int_max)

    # Range filter
    r_min = get_val("range_min", "range_min")
    r_max = get_val("range_max", "range_max")
    range_dist = None
    if r_min is not None or r_max is not None:
        origin = tuple(args.origin) if args.origin else None
        range_dist = RangeParams(
            min_distance=r_min, max_distance=r_max,
            manual_origin=origin
        )

    # Voxel filter
    v_size = get_val("voxel_size", "voxel_size")
    voxel = None
    if v_size is not None:
        voxel = VoxelParams(cell_size=v_size)

    # Color cleaning
    color_clean = None
    if args.color_clean or args.ortho_path:
        color_clean = ColorCleanParams(
            enabled=True,
            ortho_path=args.ortho_path,
            threshold=args.color_threshold
        )

    # Duplicate filter: auto-enable when merging or explicit flag
    duplicate = None
    if args.deduplicate or args.merge:
        duplicate = DuplicateParams(enabled=True)

    # Classification filter
    classification = None
    if args.keep_classes:
        classification = ClassificationParams(keep_codes=list(args.keep_classes))

    return FilterOptions(
        incidence=incidence,
        intensity=intensity,
        range_dist=range_dist,
        voxel=voxel,
        color_clean=color_clean,
        duplicate=duplicate,
        classification=classification,
        preset_name=args.preset
    )


def process_single_file(input_path: str, output_path: str, opt: FilterOptions, dry_run: bool) -> int:
    """Build and execute pipeline for a single file."""
    pipeline_dict = build_pipeline(input_path, output_path, opt)

    if dry_run:
        print(f"--- DRY RUN: Pipeline for {input_path} ---")
        print(json.dumps(pipeline_dict, indent=4))
        return 0

    print(f"Processing: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
    result = execute_pipeline(pipeline_dict)
    
    if result["success"]:
        return result["points_processed"]
    else:
        print(f"Failed: {result['error']}", file=sys.stderr)
        return -1

def process_file_worker(f_path: str, session_dir: str, filter_params: FilterOptions, dry_run: bool) -> Tuple[int, str]:
    """並列処理のための独立したワーカー関数"""
    out_name = os.path.basename(f_path)
    base, ext = os.path.splitext(out_name)
    if ext.lower() == ".e57":
        out_name = base + ".las"
    
    t_path = os.path.join(session_dir, out_name)
    try:
        # process_single_file は外側でも呼べます
        pts_count = process_single_file(f_path, t_path, filter_params, dry_run)
        if pts_count >= 0:
            save_report(session_dir, out_name, filter_params, pts_count)
        return pts_count, out_name
    except Exception as e:
        print(f"Error processing {out_name}: {e}")
        return -1, out_name


def main():
    """Main entry point for the CLI tool with batch processing support."""
    try:
        args = parse_args(sys.argv[1:])
        filter_params = assemble_config(args)

        # Determine input files
        if os.path.isdir(args.input):
            input_files = []
            for ext in ("*.e57", "*.las", "*.laz"):
                input_files.extend(glob.glob(os.path.join(args.input, ext)))
        else:
            input_files = [args.input]

        if not input_files:
            print(f"No input files found at {args.input}")
            sys.exit(1)

        # Determine output strategy
        now_str = datetime.now().strftime("%Y%m%d_%H%M")
        is_batch = len(input_files) > 1 or os.path.isdir(args.input)


        if is_batch and not args.merge:
            # Batch mode: Create a session directory
            preset_tag = args.preset or "custom"
            session_dir = os.path.join(args.output, f"{preset_tag}_{now_str}")
            os.makedirs(session_dir, exist_ok=True)
            
            safe_workers = args.max_workers
            if safe_workers is None:
                # CPUコア数から1を引いた数を最大とする（OSのために1コア残す、最低でも1は確保）
                cpu_cores = os.cpu_count() or 4
                safe_workers = max(1, cpu_cores - 1)
                # メモリが心配な場合は、ここを min(max(1, cpu_cores - 1), 6) などにして上限を6にするのも手です

            print(f"Starting batch processing of {len(input_files)} files using {safe_workers} parallel workers...")
            
            total_processed = 0
            
            # ★ ProcessPoolExecutor を使用して並列処理を実行
            with concurrent.futures.ProcessPoolExecutor(max_workers=safe_workers) as executor:
                # 独立したワーカー関数に、必要な変数をすべて渡して予約する
                futures = {
                    executor.submit(process_file_worker, f, session_dir, filter_params, args.dry_run): f 
                    for f in input_files
                }
                
                # 処理が完了したものから順次結果を受け取る
                for future in concurrent.futures.as_completed(futures):
                    pts, fname = future.result()
                    if pts >= 0:
                        total_processed += pts
                        print(f"[Completed] {fname} ({pts} points)")
            
            print(f"\nBatch processing complete. Products saved in {session_dir}")
            print(f"Total points processed: {total_processed}")

        elif args.merge and len(input_files) > 1:
            # Merge mode: Merge all inputs into one output file
            if os.path.isdir(args.output):
                preset_tag = args.preset or "custom"
                session_dir = os.path.join(args.output, f"merged_{preset_tag}_{now_str}")
                os.makedirs(session_dir, exist_ok=True)
                output_path = os.path.join(session_dir, f"merged_{now_str}.las")
            else:
                output_path = args.output
                session_dir = os.path.dirname(output_path) or "."

            pipeline_dict = build_pipeline(input_files, output_path, filter_params, merge=True)
            
            if args.dry_run:
                print("--- DRY RUN: Merge Pipeline ---")
                print(json.dumps(pipeline_dict, indent=4))
            else:
                print(f"Merging {len(input_files)} files into {output_path}...")
                result = execute_pipeline(pipeline_dict)
                if result["success"]:
                    print(f"Success! Points merged: {result['points_processed']}")
                    save_report(session_dir, os.path.basename(output_path), filter_params, result["points_processed"])
                else:
                    print(f"Merge failed: {result['error']}", file=sys.stderr)
                    sys.exit(1)
        else:
            # Single file mode
            pts = process_single_file(args.input, args.output, filter_params, args.dry_run)
            if pts >= 0 and not args.dry_run:
                print(f"Success! Points processed: {pts}")
                out_dir = os.path.dirname(args.output) or "."
                save_report(out_dir, os.path.basename(args.output), filter_params, pts)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
