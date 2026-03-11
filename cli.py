import argparse
import sys
import os
import glob
import shutil
from datetime import datetime
from lib.filter import (
    FilterOptions, IncidenceAngleParams, RangeParams, VoxelParams,
    build_individual_pipeline, build_merge_pipeline, execute_pipeline, save_report
)

def parse_args():
    parser = argparse.ArgumentParser(
        description="GeoQuantz GSI-Compliant PointCloud Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # プリセット選択
    parser.add_argument("--preset", choices=["tls", "uav"], default="tls", help="Select sensor preset (Default: tls)")
    
    # ワークフロー制御
    parser.add_argument("--no-merge", action="store_true", help="Output individual LAS files without merging")
    
    # フィルタパラメータ
    parser.add_argument("--range-max", type=float, help="Override max distance (m)")
    parser.add_argument("--voxel-size", type=float, help="Override voxel size (m)")
    parser.add_argument("--color-clean", action="store_true", help="Enable ortho-based ghost removal")
    parser.add_argument(
        "--color-threshold", 
        type=float, 
        help=(
            "Color difference threshold (0-255). Lower is stricter. "
            "50: Aggressive (High risk), 80-100: Standard, 120-150: Loose (Safe)"
        )
    )
    
    # パス設定
    parser.add_argument("-i", "--input", default="01_raw", help="Input directory (Default: 01_raw)")
    parser.add_argument("-o", "--output", default="04_product", help="Output root directory")
    parser.add_argument("--ortho", default="02_ref/ortho/katsuoka_ortho.tif", help="Path to reference ortho")

    return parser.parse_args()

def main():
    try:
        args = parse_args()
        
        # 入力ファイルの探索 (01_raw 直下)
        input_files = glob.glob(os.path.join(args.input, "*.e57"))
        if not input_files:
            print(f"Error: No E57 files found in {os.path.abspath(args.input)}")
            sys.exit(1)

        # プリセット/パラメータの確定
        if args.preset == "tls":
            d_range = args.range_max or 15.0
            d_inc_min, d_inc_max = 4.0, 86.0
            d_voxel = args.voxel_size or 0.01
            d_color_th = args.color_threshold or 120.0
        else:
            d_range = args.range_max or 60.0
            d_inc_min, d_inc_max = 4.0, 45.0
            d_voxel = args.voxel_size or 0.10
            d_color_th = args.color_threshold or 80.0

        now_str = datetime.now().strftime("%Y%m%d_%H%M")
        session_name = f"{args.preset}_{now_str}"
        output_session_dir = os.path.join(args.output, session_name)
        os.makedirs(output_session_dir, exist_ok=True)

        is_merging = not args.no_merge
        temp_dir = os.path.join("03_work", f"_temp_{session_name}") if is_merging else output_session_dir
        if is_merging:
            os.makedirs(temp_dir, exist_ok=True)

        opt = FilterOptions(
            preset_name=args.preset,
            incidence=IncidenceAngleParams(min_angle=d_inc_min, max_angle=d_inc_max),
            range_dist=RangeParams(max_distance=d_range),
            voxel=VoxelParams(cell_size=d_voxel),
            color_clean=args.color_clean,
            color_threshold=d_color_th,
            ortho_path=args.ortho
        )

        processed_files = []
        # Phase 1: 個別フィルタリング
        for i, f in enumerate(input_files):
            out_name = os.path.basename(f).replace(".e57", ".las")
            target_path = os.path.join(temp_dir, out_name)
            print(f"[{i+1}/{len(input_files)}] Phase 1: Processing {os.path.basename(f)}")
            execute_pipeline(build_individual_pipeline(f, target_path, opt))
            processed_files.append(target_path)

        # Phase 2: マージと最終処理
        if is_merging:
            file_tag = f"GQ_{args.preset.upper()}_R{int(d_range)}_V{int(d_voxel*1000)}mm"
            final_name = f"{file_tag}_{now_str}.las"
            final_path = os.path.join(output_session_dir, final_name)
            
            print(f"Phase 2: Merging -> {final_name}")
            total_pts = execute_pipeline(build_merge_pipeline(processed_files, final_path, opt))
            
            save_report(output_session_dir, final_name, opt, total_pts)
            
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            print(f"Success! Merged product saved in {output_session_dir}")
        else:
            print(f"Success! Individual products saved in {output_session_dir}")

    except Exception as e:
        print(f"CLI Error: {e}")

if __name__ == "__main__":
    main()