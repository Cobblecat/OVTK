"""Read-only source loading and provenance validation for Phase 5."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from operational_variance_toolkit.errors import DatabaseError, DataValidationError
from operational_variance_toolkit.storage.csv_codec import decode_csv_text, manifest_csv_codec
from operational_variance_toolkit.storage.database import connect_readonly_database
from operational_variance_toolkit.wms.storage.repositories import WmsFoundationRepository

RECONSTRUCTION_FILES = (
    "inventory_event_ledger.csv",
    "inventory_reconciliation.csv",
    "pick_context.csv",
    "qa_adjustment_context.csv",
    "replenishment_context.csv",
    "selector_exposure.csv",
)

_REQUIRED_PICK_COLUMNS = {
    "run_id",
    "pick_event_id",
    "trip_id",
    "selector_id",
    "shift_code",
    "operating_date_local",
    "item_id",
    "velocity_class",
    "fragility_score",
    "pick_location_id",
    "zone_code",
    "aisle_code",
    "event_utc",
    "requested_qty_cases",
    "picked_qty_cases",
    "short_qty_cases",
    "short_flag",
    "eligible_pick_flag",
    "system_qty_before_cases",
    "active_replenishment_at_pick_flag",
    "minutes_to_nearest_replenishment_completion",
    "replenishment_adjacent_flag",
    "recent_qa_event_count_4h",
    "recent_adjustment_count_4h",
    "system_event_overlap_flag",
}

_REQUIRED_RECONSTRUCTION_COLUMNS = {
    "inventory_reconciliation": {
        "run_id",
        "location_id",
        "difference_to_live_cases",
        "difference_to_snapshot_cases",
        "reconciliation_status",
    },
    "replenishment_context": {
        "run_id",
        "replenishment_task_id",
        "creation_to_confirmation_minutes",
        "confirmed_qty_cases",
        "source_balance_before_cases",
        "source_balance_after_cases",
        "destination_balance_before_cases",
        "destination_balance_after_cases",
    },
    "qa_adjustment_context": {"run_id", "qa_event_id", "adjustment_id"},
    "selector_exposure": {"run_id", "selector_id", "eligible_pick_lines"},
}

_UNIQUE_GRAINS = {
    "pick_context": "pick_event_id",
    "inventory_reconciliation": "location_id",
    "replenishment_context": "replenishment_task_id",
    "qa_adjustment_context": "qa_event_id",
    "selector_exposure": "selector_id",
}

_FORBIDDEN_COLUMN_TOKENS = (
    "ground_truth",
    "true_root_cause",
    "is_injected",
    "hidden_physical",
    "scenario_name",
    "scenario_version",
)


@dataclass(frozen=True, slots=True)
class StatisticalSource:
    database_path: Path
    reconstruction_path: Path
    source_sha256: str
    reconstruction_manifest_sha256: str
    metadata: dict[str, Any]
    reconstruction_manifest: dict[str, Any]
    tables: dict[str, pd.DataFrame]


def load_statistical_source(
    database_path: str | Path,
    reconstruction_path: str | Path,
) -> StatisticalSource:
    """Load a schema-3 source and its verified reconstruction without mutation."""

    database = _require_safe_file(database_path, "database")
    reconstruction = _require_safe_directory(reconstruction_path)
    source_sha256 = sha256_file(database)
    manifest_path = reconstruction / "analysis_manifest.json"
    if not manifest_path.is_file():
        raise DataValidationError(f"Reconstruction manifest does not exist: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError(f"Malformed reconstruction manifest: {manifest_path}") from exc

    codec = manifest_csv_codec(manifest, kind="reconstruction")
    _validate_manifest(manifest, source_sha256, reconstruction)
    tables = {
        Path(file_name).stem: pd.read_csv(reconstruction / file_name)
        for file_name in RECONSTRUCTION_FILES
    }
    if codec is not None:
        for frame in tables.values():
            for column in frame:
                if pd.api.types.is_string_dtype(frame[column].dtype):
                    frame[column] = frame[column].map(
                        lambda value: decode_csv_text(value, codec), na_action="ignore"
                    )

    try:
        with closing(connect_readonly_database(database)) as connection:
            repository = WmsFoundationRepository(connection)
            if repository.user_version() != 3:
                raise DataValidationError("Statistical analysis requires a schema-3 WMS database")
            metadata_record = repository.run_metadata()
            metadata = {
                "run_id": metadata_record.run_id,
                "schema_version": metadata_record.schema_version,
                "generator_version": metadata_record.generator_version,
                "config_hash": metadata_record.config_hash,
                "seed": metadata_record.seed,
                "facility_timezone": metadata_record.facility_timezone,
                "simulation_start_utc": metadata_record.simulation_start_utc,
                "simulation_end_utc": metadata_record.simulation_end_utc,
            }
            eligibility = pd.read_sql_query(
                "SELECT pick_event_id, eligible_pick_flag FROM pick_event ORDER BY pick_event_id",
                connection,
            )
            tables["pick_context"] = tables["pick_context"].merge(
                eligibility,
                on="pick_event_id",
                how="left",
                validate="one_to_one",
            )
            tables.update(
                {
                    "qa_event": pd.read_sql_query(
                        "SELECT * FROM qa_event ORDER BY event_sequence, qa_event_id",
                        connection,
                    ),
                    "inventory_adjustment": pd.read_sql_query(
                        "SELECT * FROM inventory_adjustment ORDER BY event_sequence, adjustment_id",
                        connection,
                    ),
                    "item_master": pd.read_sql_query(
                        "SELECT * FROM item_master ORDER BY item_id", connection
                    ),
                }
            )
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Malformed or unsupported statistical database: {database}") from exc
    except pd.errors.MergeError as exc:
        raise DataValidationError("Pick eligibility grain does not match reconstruction") from exc

    _validate_source_tables(metadata, manifest, tables)
    return StatisticalSource(
        database_path=database,
        reconstruction_path=reconstruction,
        source_sha256=source_sha256,
        reconstruction_manifest_sha256=sha256_file(manifest_path),
        metadata=metadata,
        reconstruction_manifest=manifest,
        tables=tables,
    )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_safe_file(path: str | Path, label: str) -> Path:
    value = Path(path)
    _reject_restricted_path(value)
    if not value.is_file():
        raise DatabaseError(f"Statistical {label} does not exist or is not a file: {value}")
    return value.resolve()


def _require_safe_directory(path: str | Path) -> Path:
    value = Path(path)
    _reject_restricted_path(value)
    if not value.is_dir():
        raise DataValidationError(
            f"Reconstruction path does not exist or is not a directory: {value}"
        )
    return value.resolve()


def _reject_restricted_path(path: Path) -> None:
    lowered = str(path).lower()
    if "ground_truth" in lowered or "restricted" in lowered:
        raise DataValidationError("Ordinary statistical analysis refuses restricted-truth paths")


def _validate_manifest(manifest: dict[str, Any], source_sha256: str, reconstruction: Path) -> None:
    if manifest.get("artifact_type") != "analysis_reconstruction":
        raise DataValidationError("Unsupported reconstruction artifact type")
    if manifest.get("reconstruction_version") != "2.0.0":
        raise DataValidationError("Statistical analysis requires reconstruction version 2.0.0")
    source = manifest.get("source", {})
    if source.get("schema_version") != "3.0.0":
        raise DataValidationError("Statistical analysis requires schema version 3.0.0")
    if source.get("sha256") != source_sha256:
        raise DataValidationError("Database checksum does not match reconstruction manifest")
    outputs = manifest.get("outputs", {})
    for file_name in RECONSTRUCTION_FILES:
        path = reconstruction / file_name
        if not path.is_file():
            raise DataValidationError(f"Required reconstruction output is missing: {file_name}")
        expected = outputs.get(file_name, {}).get("sha256")
        if expected != sha256_file(path):
            raise DataValidationError(f"Reconstruction output checksum mismatch: {file_name}")
        expected_rows = outputs.get(file_name, {}).get("rows")
        if not isinstance(expected_rows, int) or expected_rows < 0:
            raise DataValidationError(f"Invalid reconstruction row count: {file_name}")


def _validate_source_tables(
    metadata: dict[str, Any], manifest: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> None:
    source = manifest["source"]
    for key, metadata_key in (
        ("run_id", "run_id"),
        ("schema_version", "schema_version"),
        ("configuration_sha256", "config_hash"),
        ("generator_version", "generator_version"),
    ):
        if source.get(key) != metadata.get(metadata_key):
            raise DataValidationError(f"Reconstruction/database identity mismatch for {key}")

    picks = tables["pick_context"]
    missing = sorted(_REQUIRED_PICK_COLUMNS - set(picks.columns))
    if missing:
        raise DataValidationError(f"Pick context is missing required columns: {missing}")
    for table_name, required_columns in _REQUIRED_RECONSTRUCTION_COLUMNS.items():
        missing_columns = sorted(required_columns - set(tables[table_name].columns))
        if missing_columns:
            raise DataValidationError(
                f"{table_name} is missing required columns: {missing_columns}"
            )
    for table_name, grain in _UNIQUE_GRAINS.items():
        if tables[table_name][grain].duplicated().any():
            raise DataValidationError(f"{table_name} contains duplicate {grain} values")
    for file_name in RECONSTRUCTION_FILES:
        table_name = Path(file_name).stem
        expected_rows = manifest["outputs"][file_name]["rows"]
        if len(tables[table_name]) != expected_rows:
            raise DataValidationError(f"Reconstruction row count mismatch: {file_name}")
    if set(picks["run_id"].astype(str)) != {metadata["run_id"]}:
        raise DataValidationError("Pick context run identity does not match database")
    if picks[list(_REQUIRED_PICK_COLUMNS)].isna().any().any():
        nullable = {"minutes_to_nearest_replenishment_completion"}
        required_nonnull = sorted(_REQUIRED_PICK_COLUMNS - nullable)
        if picks[required_nonnull].isna().any().any():
            raise DataValidationError(
                "Pick context has missing values in required analytical fields"
            )
    for quantity in ("requested_qty_cases", "picked_qty_cases", "short_qty_cases"):
        if not pd.api.types.is_numeric_dtype(picks[quantity]):
            raise DataValidationError(f"Pick context has nonnumeric {quantity}")
        if (picks[quantity] < 0).any():
            raise DataValidationError(f"Pick context has negative {quantity}")
    if not (
        picks["requested_qty_cases"] == picks["picked_qty_cases"] + picks["short_qty_cases"]
    ).all():
        raise DataValidationError("Pick requested quantity does not reconcile to picked plus short")

    reconciliation = tables["inventory_reconciliation"]
    if set(reconciliation["reconciliation_status"].astype(str)) != {"PASS"}:
        raise DataValidationError("Reconstruction contains non-PASS inventory reconciliation")
    if (
        (reconciliation[["difference_to_live_cases", "difference_to_snapshot_cases"]] != 0)
        .any()
        .any()
    ):
        raise DataValidationError("Reconstruction is not exact across replay/live/snapshot")

    for table_name, table in tables.items():
        for column in table.columns:
            lowered = column.lower()
            if any(token in lowered for token in _FORBIDDEN_COLUMN_TOKENS):
                raise DataValidationError(f"Forbidden hidden-truth field in {table_name}: {column}")
