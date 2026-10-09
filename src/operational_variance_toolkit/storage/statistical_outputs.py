"""Atomic deterministic writers for frozen Phase 5 outputs."""

from __future__ import annotations

import csv
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from operational_variance_toolkit.analysis.statistical_config import AnalysisConfig
from operational_variance_toolkit.analysis.statistics import OUTPUT_COLUMNS, StatisticalAnalysis
from operational_variance_toolkit.errors import DatabaseError, OutputExistsError
from operational_variance_toolkit.storage.statistical_sources import sha256_file


@dataclass(frozen=True, slots=True)
class StatisticalOutputWriteResult:
    output_path: Path
    file_checksums: dict[str, str]


def require_available_statistics_output(output_path: str | Path) -> Path:
    """Refuse an existing nonempty statistics output before analysis begins."""

    path = Path(output_path)
    if path.exists():
        if not path.is_dir():
            raise OutputExistsError(f"Statistics output exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise OutputExistsError(
                f"Statistics output directory already exists and is not empty: {path}"
            )
    return path


def write_statistical_outputs(
    output_path: str | Path,
    analysis: StatisticalAnalysis,
    config: AnalysisConfig,
    manifest: dict[str, Any],
) -> StatisticalOutputWriteResult:
    """Write frozen outputs through a temporary sibling directory."""

    final_path = require_available_statistics_output(output_path)
    temporary_path = final_path.parent / (
        f".{final_path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:12]}"
    )
    try:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.mkdir()
        checksums: dict[str, str] = {}
        outputs: dict[str, dict[str, Any]] = {}
        config_path = temporary_path / "analysis_config.json"
        config_path.write_text(config.canonical_json(), encoding="utf-8")
        checksums[config_path.name] = sha256_file(config_path)
        outputs[config_path.name] = {"rows": 1, "sha256": checksums[config_path.name]}

        for file_name, rows in analysis.tables.items():
            path = temporary_path / file_name
            _write_csv(path, OUTPUT_COLUMNS[file_name], rows)
            checksums[file_name] = sha256_file(path)
            outputs[file_name] = {"rows": len(rows), "sha256": checksums[file_name]}

        diagnostics_path = temporary_path / "model_diagnostics.json"
        diagnostics_path.write_text(
            json.dumps(analysis.model_diagnostics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        checksums[diagnostics_path.name] = sha256_file(diagnostics_path)
        outputs[diagnostics_path.name] = {
            "rows": 1,
            "sha256": checksums[diagnostics_path.name],
        }

        manifest_payload = {**manifest, "outputs": outputs}
        manifest_path = temporary_path / "analysis_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        checksums[manifest_path.name] = sha256_file(manifest_path)
        if final_path.exists():
            final_path.rmdir()
        temporary_path.rename(final_path)
        return StatisticalOutputWriteResult(final_path.resolve(), checksums)
    except Exception as exc:
        if temporary_path.exists():
            shutil.rmtree(temporary_path, ignore_errors=True)
        if isinstance(exc, OutputExistsError):
            raise
        raise DatabaseError(f"Failed to write statistical outputs at {final_path}: {exc}") from exc


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _serialize(row[column]) for column in columns})


def _serialize(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    return value
