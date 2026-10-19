"""Resolve logical tool environments into tested physical environment profiles."""

from functools import lru_cache
import json
import os
import sys
from pathlib import Path


@lru_cache(maxsize=1)
def profiles():
    from scitoolflow.paths import project_root

    return json.loads(
        (project_root() / "configs/environments/routing.json").read_text()
    )


def selected_profile():
    name = os.getenv("SCITOOL_ENV_PROFILE", "integrated")
    if name not in profiles()["profiles"]:
        raise ValueError(
            f"Unknown or retired environment profile: {name}; use integrated"
        )
    return name


def tool_environment(logical_name):
    override = os.getenv("SCITOOL_TOOL_ENV_" + logical_name.replace("-", "_").upper())
    return override or profiles()["profiles"][selected_profile()].get(
        logical_name, logical_name
    )


def environment_python(environment):
    """Resolve named environments from either a project environment or Conda base."""
    explicit = os.getenv("SCITOOL_CONDA_ENVS_PATH")
    if explicit:
        return Path(explicit) / environment / "bin/python"
    prefix = Path(sys.prefix)
    if prefix.name == environment:
        return Path(sys.executable)
    # Named Conda environments sit under envs/; Conda base owns that directory.
    base = prefix / "envs" if (prefix / "envs").is_dir() else prefix.parent
    return base / environment / "bin/python"
