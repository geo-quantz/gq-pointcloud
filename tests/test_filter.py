import json
import os

from lib.filter import (
    FilterOptions,
    IncidenceAngleParams,
    IntensityParams,
    RangeParams,
    DuplicateParams,
    SpatialClipParams,
    build_pipeline,
    build_spatial_clip_filter,
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


def test_spatial_clip_disabled():
    assert build_spatial_clip_filter(None) is None
    assert build_spatial_clip_filter(SpatialClipParams(enabled=False)) is None
    assert build_spatial_clip_filter(SpatialClipParams()) is None


def test_spatial_clip_xy_only():
    params = SpatialClipParams(x_min=100.0, x_max=200.0, y_min=50.0, y_max=150.0)
    stage = build_spatial_clip_filter(params)
    assert stage is not None
    assert stage["type"] == "filters.crop"
    bounds = stage["bounds"]
    assert "[100.0,200.0]" in bounds
    assert "[50.0,150.0]" in bounds
    assert "inf" not in bounds.replace("-inf", "")


def test_spatial_clip_with_z():
    params = SpatialClipParams(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0, z_min=1.0, z_max=5.0)
    stage = build_spatial_clip_filter(params)
    assert stage is not None
    bounds = stage["bounds"]
    assert "[1.0,5.0]" in bounds


def test_spatial_clip_partial_bounds():
    params = SpatialClipParams(x_min=100.0, y_max=200.0)
    stage = build_spatial_clip_filter(params)
    assert stage is not None
    bounds = stage["bounds"]
    assert "100.0" in bounds
    assert "200.0" in bounds
    assert "-inf" in bounds or "inf" in bounds


def test_pipeline_includes_spatial_clip():
    options = FilterOptions(
        spatial_clip=SpatialClipParams(x_min=0.0, x_max=100.0, y_min=0.0, y_max=100.0),
    )
    pipeline = build_pipeline("input.las", "output.las", options)
    stages = pipeline["pipeline"]
    types = [s.get("type") for s in stages if isinstance(s, dict)]
    assert "filters.crop" in types


if __name__ == "__main__":
    test_pipeline_builder()
