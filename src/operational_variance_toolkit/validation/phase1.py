"""Phase 1 dataset validation."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from operational_variance_toolkit.storage.repositories import (
    PHASE1_TABLES,
    Phase1DatasetRepository,
)
from operational_variance_toolkit.storage.schema import SCHEMA_VERSION
from operational_variance_toolkit.validation.result import ValidationIssue, ValidationResult

_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "schema_metadata": {"schema_version", "created_at_utc"},
    "simulation_run": {
        "run_id",
        "scenario_name",
        "scenario_version",
        "seed",
        "schema_version",
        "generator_version",
        "config_hash",
        "facility_timezone",
        "simulation_start_utc",
        "simulation_end_utc",
        "generated_at_utc",
    },
    "facility": {"run_id", "facility_id", "facility_name", "timezone"},
    "zone": {"run_id", "zone_id", "facility_id", "zone_code", "active_flag"},
    "location": {
        "run_id",
        "location_id",
        "zone_id",
        "location_type",
        "capacity_cases",
        "pickable_flag",
        "active_flag",
    },
    "item": {
        "run_id",
        "item_id",
        "item_description",
        "required_zone_code",
        "cases_per_pallet",
        "velocity_class",
        "active_flag",
    },
    "operator": {"run_id", "operator_id", "role", "shift_code", "active_flag"},
    "shift": {"run_id", "shift_id", "facility_id", "start_utc", "end_utc"},
    "slot_assignment": {
        "run_id",
        "assignment_id",
        "item_id",
        "pick_location_id",
        "effective_start_utc",
        "target_cases",
        "maximum_cases",
    },
    "work_assignment": {"run_id", "work_assignment_id", "operator_id", "shift_id", "role"},
    "handling_unit": {"run_id", "handling_unit_id", "item_id", "initial_qty_cases", "status"},
    "inventory_snapshot": {
        "run_id",
        "snapshot_id",
        "snapshot_utc",
        "snapshot_type",
        "item_id",
        "location_id",
        "handling_unit_id",
        "qty_cases",
        "source_code",
    },
}


def validate_phase1_dataset(connection: sqlite3.Connection) -> ValidationResult:
    """Validate a Phase 1 analyst-facing database."""

    repository = Phase1DatasetRepository(connection)
    failures: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    failures.extend(_validate_schema(repository))
    if failures:
        return ValidationResult(tuple(failures), tuple(warnings))

    failures.extend(_validate_metadata(repository))
    failures.extend(_validate_foreign_keys(repository))
    failures.extend(_validate_required_values(repository))
    failures.extend(_validate_master_data(repository))
    failures.extend(_validate_opening_inventory(repository))

    warnings.extend(_validate_noncritical_state(repository))
    return ValidationResult(tuple(failures), tuple(warnings))


def _validate_schema(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    failures: list[ValidationIssue] = []
    table_names = repository.table_names()
    missing_tables = [table_name for table_name in PHASE1_TABLES if table_name not in table_names]
    if missing_tables:
        failures.append(
            ValidationIssue("schema", f"Missing required table(s): {', '.join(missing_tables)}")
        )
        return failures

    if repository.user_version() != 1:
        failures.append(
            ValidationIssue(
                "schema",
                f"Unsupported SQLite user_version: {repository.user_version()}",
            )
        )

    schema_versions = repository.schema_versions()
    if schema_versions != [SCHEMA_VERSION]:
        failures.append(
            ValidationIssue(
                "schema",
                f"Unsupported schema_metadata version(s): {', '.join(schema_versions) or 'none'}",
            )
        )

    for table_name, required_columns in _REQUIRED_COLUMNS.items():
        missing_columns = sorted(required_columns - repository.table_columns(table_name))
        if missing_columns:
            failures.append(
                ValidationIssue(
                    "schema",
                    f"{table_name} missing required column(s): {', '.join(missing_columns)}",
                )
            )
    return failures


def _validate_metadata(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    rows = repository.run_metadata_rows()
    if len(rows) != 1:
        return [
            ValidationIssue(
                "metadata", f"Expected exactly one simulation_run row, found {len(rows)}"
            )
        ]

    row = rows[0]
    failures: list[ValidationIssue] = []
    if row.schema_version != SCHEMA_VERSION:
        failures.append(
            ValidationIssue("metadata", f"Run schema_version is unsupported: {row.schema_version}")
        )
    if row.simulation_start_utc >= row.simulation_end_utc:
        failures.append(
            ValidationIssue("metadata", "simulation_start_utc must be before simulation_end_utc")
        )
    return failures


def _validate_foreign_keys(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    violations = repository.foreign_key_violations()
    if not violations:
        return []
    return [
        ValidationIssue(
            "foreign_keys",
            f"Foreign-key violation(s): {len(violations)}",
        )
    ]


def _validate_required_values(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    return [
        ValidationIssue("required_values", f"{table}.{column} has {count} null value(s)")
        for table, column, count in repository.null_violations()
    ]


def _validate_master_data(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    return _issues_from_counts("master_data", repository.master_data_violations())


def _validate_opening_inventory(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    return _issues_from_counts("opening_inventory", repository.opening_inventory_violations())


def _validate_noncritical_state(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    counts = repository.table_counts()
    return [
        ValidationIssue("dataset", f"{table_name} is empty")
        for table_name in PHASE1_TABLES
        if counts.get(table_name, 0) == 0
    ]


def _issues_from_counts(
    category: str, violations: Iterable[tuple[str, int]]
) -> list[ValidationIssue]:
    return [
        ValidationIssue(category, f"{message}: {count} row(s)") for message, count in violations
    ]
