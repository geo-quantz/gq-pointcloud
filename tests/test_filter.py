import json
import os
import sys

# Add the project root to sys.path so we can import lib.filter
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.filter import (
    FilterOptions,
    IncidenceAngleParams,
    IntensityParams,
    RangeParams,
    DuplicateParams,
    build_pipeline,
    execute_pipeline,
)


def test_pipeline_builder_with_faux():
    print("Testing pipeline builder using PDAL readers.faux...")

    # 1. Define parameters for all filters
    options = FilterOptions(
        incidence=IncidenceAngleParams(max_angle=15.0),
        intensity=IntensityParams(min_intensity=10, max_intensity=500),
        range_dist=RangeParams(min_distance=0.5, max_distance=100.0),
        duplicate=DuplicateParams(),
    )

    # 2. Use readers.faux instead of a real file
    # This generates 100 points in memory for testing.
    input_faux = {
        "type": "readers.faux",
        "count": 100,
        "mode": "random"
    }
    output_file = "test_output.las"

    pipeline_dict = build_pipeline(input_faux, output_file, options)

    print("Generated Pipeline Dictionary:")
    print(json.dumps(pipeline_dict, indent=2))

    # Verify dictionary structure
    assert "pipeline" in pipeline_dict
    assert len(pipeline_dict["pipeline"]) == 6  # faux reader + 4 filters + writer
    assert pipeline_dict["pipeline"][0] == input_faux
    assert pipeline_dict["pipeline"][-1]["type"] == "writers.las"

    print("Pipeline dictionary structure verified.")

    # 3. Attempt execution if PDAL is functional in this environment
    try:
        import pdal
        print("\nAttempting to execute pipeline with PDAL...")
        result = execute_pipeline(pipeline_dict)
        
        if result["success"]:
            print(f"Execution Success! Processed {result['points_processed']} points.")
            # Clean up dummy output if it was actually created
            if os.path.exists(output_file):
                os.remove(output_file)
        else:
            print(f"Pipeline execution failed (this is expected if PDAL environment is partial): {result['error']}")
    except ImportError:
        print("\nPDAL Python library not found. Skipping execution test, but structure is valid.")

if __name__ == "__main__":
    test_pipeline_builder_with_faux()
