import argparse
import json
import sys
from typing import List

from lib.filter import (
    DuplicateParams,
    FilterOptions,
    IncidenceAngleParams,
    IntensityParams,
    RangeParams,
    StatisticalOutlierParams,
    build_pipeline,
    execute_pipeline,
)


def parse_args(args: List[str]) -> argparse.Namespace:
    """Parses command-line arguments for the PDAL filter pipeline."""
    parser = argparse.ArgumentParser(
        description="Execute a PDAL filter pipeline on a point cloud."
    )

    # Core IO arguments
    parser.add_argument(
        "--input", "-i", required=True, help="Path to the input point cloud file."
    )
    parser.add_argument(
        "--output", "-o", required=True, help="Path to the output point cloud file."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated PDAL pipeline dictionary without executing it.",
    )

    # Incidence Angle Filter Group
    incidence_group = parser.add_argument_group("Incidence Angle Filter")
    incidence_group.add_argument(
        "--incidence-angle-max",
        type=float,
        help="Maximum incidence angle (uses absolute ScanAngleRank).",
    )

    # Intensity Filter Group
    intensity_group = parser.add_argument_group("Intensity Filter")
    intensity_group.add_argument(
        "--intensity-min", type=float, help="Minimum intensity value."
    )
    intensity_group.add_argument(
        "--intensity-max", type=float, help="Maximum intensity value."
    )

    # Measurement Distance (Range) Filter Group
    range_group = parser.add_argument_group("Measurement Distance Filter")
    range_group.add_argument(
        "--range-min", type=float, help="Minimum Euclidean distance from origin."
    )
    range_group.add_argument(
        "--range-max", type=float, help="Maximum Euclidean distance from origin."
    )

    # Duplicate Filter Group
    duplicate_group = parser.add_argument_group("Duplicate Filter")
    duplicate_group.add_argument(
        "--deduplicate",
        action="store_true",
        help="Enable duplicate point removal (removes exact XYZ matches).",
    )

    # Statistical Outlier Removal Group
    sor_group = parser.add_argument_group("Statistical Outlier Removal")
    sor_group.add_argument(
        "--outlier-statistical",
        action="store_true",
        help="Enable statistical outlier removal (filters.outlier method=statistical).",
    )
    sor_group.add_argument(
        "--outlier-mean-k",
        type=int,
        default=8,
        metavar="K",
        help="Number of nearest neighbors for outlier detection (default: 8).",
    )
    sor_group.add_argument(
        "--outlier-multiplier",
        type=float,
        default=2.0,
        metavar="M",
        help="Standard deviation multiplier threshold (default: 2.0).",
    )

    return parser.parse_args(args)


def assemble_config(args: argparse.Namespace) -> FilterOptions:
    """
    Maps CLI arguments to the structured FilterOptions configuration object.
    Filters are only enabled if relevant arguments are provided.
    """
    # Incidence filter: enabled if max angle is provided
    incidence = None
    if args.incidence_angle_max is not None:
        incidence = IncidenceAngleParams(max_angle=args.incidence_angle_max)

    # Intensity filter: enabled if either min or max intensity is provided
    intensity = None
    if args.intensity_min is not None or args.intensity_max is not None:
        intensity = IntensityParams(
            min_intensity=args.intensity_min, max_intensity=args.intensity_max
        )

    # Range filter: enabled if either min or max distance is provided
    range_dist = None
    if args.range_min is not None or args.range_max is not None:
        range_dist = RangeParams(
            min_distance=args.range_min, max_distance=args.range_max
        )

    # Duplicate filter: explicitly enabled via flag
    duplicate = None
    if args.deduplicate:
        duplicate = DuplicateParams(enabled=True)

    # Statistical outlier removal
    statistical_outlier = None
    if args.outlier_statistical:
        statistical_outlier = StatisticalOutlierParams(
            mean_k=args.outlier_mean_k,
            multiplier=args.outlier_multiplier,
        )

    return FilterOptions(
        incidence=incidence,
        intensity=intensity,
        range_dist=range_dist,
        duplicate=duplicate,
        statistical_outlier=statistical_outlier,
    )


def main():
    """Main entry point for the CLI tool."""
    try:
        args = parse_args(sys.argv[1:])
        filter_params = assemble_config(args)

        # Build the pipeline dictionary using the existing builder logic
        pipeline_dict = build_pipeline(args.input, args.output, filter_params)

        if args.dry_run:
            print("--- DRY RUN: Generated PDAL Pipeline ---")
            print(json.dumps(pipeline_dict, indent=4))
            return

        # Execute the pipeline using the existing executor logic
        print(f"Executing pipeline: {args.input} -> {args.output}")
        result = execute_pipeline(pipeline_dict)

        if result["success"]:
            print("Pipeline execution completed successfully.")
            print(f"Points processed: {result['points_processed']}")
            if "note" in result:
                print(f"Note: {result['note']}")
        else:
            print(f"Pipeline execution failed: {result['error']}", file=sys.stderr)
            if result.get("log"):
                print(f"Log: {result['log']}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
