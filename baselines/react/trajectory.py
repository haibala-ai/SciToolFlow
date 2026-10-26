"""Trajectory readers and scientific-call projection."""

from pathlib import Path
import json
from src.utils.io import atomic_json


def scientific_calls(calls):
    return [c for c in calls if c.get("tool") != "DescribeTools"]


def load_trajectory(path):
    value = json.loads(Path(path).read_text())
    if value.get("schema_version") != "scitoolflow.trajectory.v1":
        raise ValueError("Unsupported trajectory format")
    return value
