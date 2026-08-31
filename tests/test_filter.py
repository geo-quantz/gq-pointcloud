import json
import os

from lib.filter import (
    FilterOptions,
    IncidenceAngleParams,
    IntensityParams,
    RangeParams,
    DuplicateParams,
    RadiusOutlierParams,
    build_pipeline,
    build_radius_outlier_filter,
    execute_pipeline,
)


def test_pipeline_builder():
    print("Testing pipeline builder...")

    # 1. Define parameters
    options = FilterOptions(
        incidence=IncidenceAngleParams(max_angle=15.0),
        intensity=IntensityParams(min_intensity=10, max_intensity=500),
        range_dist=RangeParams(min_distance=0.5, max_distance=100.0),
        duplicate=DuplicateParams(),
    )

    # 2. Build pipeline
    input_file = "../clamped.las"
    output_file = "test_output.las"

    # Ensure input file exists or use a dummy for structure test
    if not os.path.exists(input_file):
        print(
            f"Warning: {input_file} not found. Test will only verify dictionary structure."
        )
        # Create a tiny valid LAS if possible? Better to just check dict.

    pipeline_dict = build_pipeline(input_file, output_file, options)

    print("Generated Pipeline Dictionary:")
    print(json.dumps(pipeline_dict, indent=2))

    # Verify structure
    assert "pipeline" in pipeline_dict
    # input + range(1) + normal(1) + incidence(1) + intensity(1) + duplicate(2) + writer(1) = 8
    assert len(pipeline_dict["pipeline"]) == 8
    assert pipeline_dict["pipeline"][0] == input_file
    assert pipeline_dict["pipeline"][-1]["type"] == "writers.las"

    print("Pipeline dictionary structure verified.")

    # 3. Test execution (only if file exists)
    if os.path.exists(input_file):
        print("\nExecuting pipeline...")
        result = execute_pipeline(pipeline_dict)
        if result["success"]:
            print(f"Success! Processed {result['points_processed']} points.")
            if os.path.exists(output_file):
                print(f"Output file {output_file} created.")
                os.remove(output_file)
        else:
            print(f"Pipeline execution failed: {result['error']}")
            # It might fail if 'Distance' dimension is missing, which is expected for standard LAS.
            if "Distance" in result["error"]:
                print("Note: 'Distance' dimension failure is expected if not in LAS.")


def test_radius_outlier_filter_disabled():
    assert build_radius_outlier_filter(None) is None
    assert build_radius_outlier_filter(RadiusOutlierParams(enabled=False)) is None


def test_radius_outlier_filter_defaults():
    stages = build_radius_outlier_filter(RadiusOutlierParams())
    # Returns a two-stage list: [filters.outlier, filters.expression]
    assert stages is not None
    assert isinstance(stages, list)
    assert len(stages) == 2
    outlier_stage = stages[0]
    assert outlier_stage["type"] == "filters.outlier"
    assert outlier_stage["method"] == "radius"
    assert outlier_stage["radius"] == 1.0
    assert outlier_stage["min_k"] == 2
    expression_stage = stages[1]
    assert expression_stage["type"] == "filters.expression"
    assert "Classification != 7" in expression_stage["expression"]


def test_radius_outlier_filter_custom():
    stages = build_radius_outlier_filter(RadiusOutlierParams(radius=0.5, min_k=5))
    assert isinstance(stages, list)
    assert stages[0]["radius"] == 0.5
    assert stages[0]["min_k"] == 5
    # Expression stage must still be present
    assert stages[1]["type"] == "filters.expression"


def test_pipeline_includes_radius_outlier():
    options = FilterOptions(
        radius_outlier=RadiusOutlierParams(radius=0.5, min_k=3),
    )
    pipeline = build_pipeline("input.las", "output.las", options)
    stages = pipeline["pipeline"]
    types = [s.get("type") for s in stages if isinstance(s, dict)]
    # Both the marker stage and the removal expression must be present
    assert "filters.outlier" in types
    assert "filters.expression" in types
    outlier_stage = next(s for s in stages if isinstance(s, dict) and s.get("type") == "filters.outlier")
    assert outlier_stage["method"] == "radius"
    expr_stage = next(s for s in stages if isinstance(s, dict) and s.get("type") == "filters.expression")
    assert "Classification != 7" in expr_stage["expression"]


if __name__ == "__main__":
    test_pipeline_builder()
