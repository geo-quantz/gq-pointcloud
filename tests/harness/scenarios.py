"""
Harness scenarios: what filter combinations to run against each fixture.

Each scenario is a dict with:
  name           str   — unique name within a fixture
  filter_params  dict  — passed to lib.filter and reference.build_reference_pipeline()
  description    str   — human-readable intent (not a pass/fail criterion)
"""
from __future__ import annotations

SCENARIOS: list[dict] = [
    {
        "name": "incidence_angle_15",
        "description": "Keep only near-nadir returns (|ScanAngleRank| ≤ 15°)",
        "filter_params": {
            "incidence_angle_max": 15.0,
        },
    },
    {
        "name": "intensity_10_500",
        "description": "Keep returns with intensity in [10, 500]",
        "filter_params": {
            "intensity_min": 10.0,
            "intensity_max": 500.0,
        },
    },
    {
        "name": "duplicate_removal",
        "description": "Remove exact duplicate XYZ points",
        "filter_params": {
            "duplicate": True,
        },
    },
    {
        "name": "combined_all",
        "description": "All filters applied together (incidence + intensity + duplicate)",
        "filter_params": {
            "incidence_angle_max": 15.0,
            "intensity_min": 10.0,
            "intensity_max": 500.0,
            "duplicate": True,
        },
    },
]
