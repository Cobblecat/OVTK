"""Restricted ground-truth artifact helpers for controlled scenarios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from operational_variance_toolkit.errors import DatabaseError, OutputExistsError

GROUND_TRUTH_SCHEMA_VERSION = "1.0.0"


def write_ground_truth_artifact(path: str | Path, payload: dict[str, Any]) -> Path:
    """Write a deterministic restricted ground-truth JSON artifact."""

    artifact_path = Path(path)
    if artifact_path.exists():
        raise OutputExistsError(f"Ground-truth artifact already exists: {artifact_path}")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        artifact_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise DatabaseError(
            f"Unable to write ground-truth artifact at {artifact_path}: {exc}"
        ) from exc
    return artifact_path


def read_ground_truth_artifact(path: str | Path) -> dict[str, Any]:
    """Read a restricted ground-truth JSON artifact for scenario validation."""

    artifact_path = Path(path)
    try:
        raw = json.loads(artifact_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatabaseError(f"Ground-truth artifact does not exist: {artifact_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DatabaseError(
            f"Unable to read ground-truth artifact at {artifact_path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise DatabaseError("Ground-truth artifact root must be an object")
    return raw


def canonical_ground_truth(path: str | Path) -> str:
    """Return canonical ground-truth JSON content for reproducibility comparisons."""

    return json.dumps(read_ground_truth_artifact(path), separators=(",", ":"), sort_keys=True)
