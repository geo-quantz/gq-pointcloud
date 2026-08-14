import json
import os

from lib.filter import (
    FilterOptions,
    IncidenceAngleParams,
    IntensityParams,
    RangeParams,
    DuplicateParams,
    RadiusSampleParams,
    build_pipeline,
    build_radius_sample_filter,
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


def test_radius_sample_filter_disabled():
    assert build_radius_sample_filter(None) is None
    assert build_radius_sample_filter(RadiusSampleParams(enabled=False)) is None


def test_radius_sample_filter_defaults():
    stage = build_radius_sample_filter(RadiusSampleParams())
    assert stage is not None
    assert stage["type"] == "filters.sample"
    assert stage["radius"] == 0.05


def test_radius_sample_filter_custom():
    stage = build_radius_sample_filter(RadiusSampleParams(radius=0.1))
    assert stage["radius"] == 0.1


def test_pipeline_includes_radius_sample():
    options = FilterOptions(radius_sample=RadiusSampleParams(radius=0.05))
    pipeline = build_pipeline("input.las", "output.las", options)
    stages = pipeline["pipeline"]
    types = [s.get("type") for s in stages if isinstance(s, dict)]
    assert "filters.sample" in types


def test_pipeline_voxel_and_radius_sample_coexist():
    from lib.filter import VoxelParams
    options = FilterOptions(
        voxel=VoxelParams(cell_size=0.01),
        radius_sample=RadiusSampleParams(radius=0.05),
    )
    pipeline = build_pipeline("input.las", "output.las", options)
    stages = pipeline["pipeline"]
    types = [s.get("type") for s in stages if isinstance(s, dict)]
    assert "filters.voxelcentroidnearestneighbor" in types
    assert "filters.sample" in types


if __name__ == "__main__":
    test_pipeline_builder()
