"""Package version helpers."""

from __future__ import annotations

import tomllib
from importlib import metadata
from pathlib import Path

PACKAGE_NAME = "operational-variance-toolkit"


def get_version() -> str:
    """Return the installed distribution version.

    The fallback supports direct source-tree execution before the project is installed.
    """

    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return _read_pyproject_version()


def _read_pyproject_version() -> str:
    for parent in Path(__file__).resolve().parents:
        pyproject_path = parent / "pyproject.toml"
        if pyproject_path.exists():
            with pyproject_path.open("rb") as pyproject_file:
                data = tomllib.load(pyproject_file)
            version = data.get("project", {}).get("version")
            if isinstance(version, str) and version:
                return version
    return "0+unknown"
