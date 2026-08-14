import json
import os

from lib.filter import (
    FilterOptions,
    IncidenceAngleParams,
    IntensityParams,
    RangeParams,
    DuplicateParams,
    ClassificationParams,
    build_pipeline,
    build_classification_filter,
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
    assert len(pipeline_dict["pipeline"]) == 6  # input + 4 filters + writer
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


def test_classification_filter_disabled():
    assert build_classification_filter(None) is None
    assert build_classification_filter(ClassificationParams(enabled=False)) is None
    assert build_classification_filter(ClassificationParams(keep_codes=[])) is None


def test_classification_filter_single_code():
    stage = build_classification_filter(ClassificationParams(keep_codes=[2]))
    assert stage is not None
    assert stage["type"] == "filters.expression"
    assert "Classification == 2" in stage["expression"]


def test_classification_filter_multiple_codes():
    stage = build_classification_filter(ClassificationParams(keep_codes=[2, 6, 9]))
    assert stage is not None
    expr = stage["expression"]
    assert "Classification == 2" in expr
    assert "Classification == 6" in expr
    assert "Classification == 9" in expr
    assert "||" in expr


def test_pipeline_includes_classification():
    options = FilterOptions(
        classification=ClassificationParams(keep_codes=[2, 6]),
    )
    pipeline = build_pipeline("input.las", "output.las", options)
    stages = pipeline["pipeline"]
    expr_stages = [s for s in stages if isinstance(s, dict) and s.get("type") == "filters.expression"]
    assert any("Classification" in s.get("expression", "") for s in expr_stages)


if __name__ == "__main__":
    test_pipeline_builder()
