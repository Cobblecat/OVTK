"""Portable output writers for Phase 4 reconstruction artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from operational_variance_toolkit.analysis.reconstruction import (
    OUTPUT_FILE_NAMES,
    OUTPUT_TABLE_COLUMNS,
    ReconstructionTables,
)
from operational_variance_toolkit.errors import DatabaseError, OutputExistsError


@dataclass(frozen=True, slots=True)
class ReconstructionOutputWriteResult:
    output_path: Path
    file_checksums: dict[str, str]


def write_reconstruction_outputs(
    output_path: str | Path,
    derived: ReconstructionTables,
    manifest: Mapping[str, Any],
    *,
    table_columns: Mapping[str, tuple[str, ...]] = OUTPUT_TABLE_COLUMNS,
    file_names: Mapping[str, str] = OUTPUT_FILE_NAMES,
) -> ReconstructionOutputWriteResult:
    """Write CSV outputs and manifest through a temporary sibling directory."""

    final_path = Path(output_path)
    if final_path.exists():
        if not final_path.is_dir():
            raise OutputExistsError(
                f"Output path already exists and is not a directory: {final_path}"
            )
        if any(final_path.iterdir()):
            raise OutputExistsError(
                f"Output directory already exists and is not empty: {final_path}"
            )

    parent = final_path.parent
    temporary_path = parent / f".{final_path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:12]}"
    try:
        parent.mkdir(parents=True, exist_ok=True)
        temporary_path.mkdir()
        file_checksums: dict[str, str] = {}
        outputs: dict[str, dict[str, Any]] = {}
        for table_name, rows in derived.tables.items():
            file_name = file_names[table_name]
            csv_path = temporary_path / file_name
            _write_csv(csv_path, table_columns[table_name], rows)
            checksum = _sha256_file(csv_path)
            file_checksums[file_name] = checksum
            outputs[file_name] = {"rows": len(rows), "sha256": checksum}

        manifest_payload = dict(manifest)
        manifest_payload["outputs"] = outputs
        manifest_path = temporary_path / "analysis_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        file_checksums["analysis_manifest.json"] = _sha256_file(manifest_path)

        if final_path.exists():
            final_path.rmdir()
        temporary_path.rename(final_path)
        return ReconstructionOutputWriteResult(
            output_path=final_path,
            file_checksums=file_checksums,
        )
    except Exception as exc:
        if temporary_path.exists():
            shutil.rmtree(temporary_path, ignore_errors=True)
        if isinstance(exc, OutputExistsError):
            raise
        raise DatabaseError(
            f"Failed to write reconstruction outputs at {final_path}: {exc}"
        ) from exc


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _serialize_csv_value(row[column]) for column in columns})


def _serialize_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
