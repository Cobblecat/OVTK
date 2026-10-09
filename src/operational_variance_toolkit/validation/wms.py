"""Validation rules for schema-3 WMS datasets."""

from __future__ import annotations

import sqlite3
from math import isclose

from operational_variance_toolkit.storage.schema import WMS_SCHEMA_VERSION
from operational_variance_toolkit.validation.result import ValidationIssue, ValidationResult
from operational_variance_toolkit.wms.storage.repositories import (
    WMS_REPORT_VIEWS,
    WMS_TABLES,
    WmsFoundationRepository,
)

_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "schema_metadata": {"schema_version", "sqlite_user_version", "created_at_utc"},
    "simulation_run": {
        "run_id",
        "seed",
        "schema_version",
        "generator_version",
        "config_hash",
        "facility_timezone",
        "simulation_start_utc",
        "simulation_end_utc",
        "generated_at_utc",
    },
    "item_master": {
        "run_id",
        "item_id",
        "case_length_in",
        "case_width_in",
        "case_height_in",
        "case_cube_ft3",
        "case_weight_lb",
        "cases_per_layer",
        "layers_per_pallet",
        "cases_per_pallet",
        "required_zone_code",
        "active_flag",
    },
    "location_master": {
        "run_id",
        "location_id",
        "zone_id",
        "location_type",
        "pallet_capacity",
        "pickable_flag",
        "active_flag",
    },
    "inventory_master": {
        "run_id",
        "location_id",
        "item_id",
        "qty_on_hand_cases",
        "code_date",
        "reorder_trigger_cases",
        "minimum_qty_cases",
        "target_qty_cases",
        "maximum_qty_cases",
        "last_transaction_id",
        "last_updated_utc",
    },
    "inventory_transaction": {
        "run_id",
        "transaction_id",
        "transaction_group_id",
        "command_id",
        "event_sequence",
        "line_number",
        "transaction_type",
        "location_id",
        "item_id",
        "qty_delta_cases",
        "balance_before_cases",
        "balance_after_cases",
        "event_utc",
        "recorded_utc",
        "source_record_type",
        "source_record_id",
    },
    "wms_command": {
        "run_id",
        "command_id",
        "command_type",
        "payload_hash",
        "accepted_utc",
        "result_record_type",
        "result_record_id",
        "event_sequence",
    },
    "inventory_snapshot": {
        "run_id",
        "snapshot_batch_id",
        "snapshot_line_id",
        "snapshot_utc",
        "snapshot_type",
        "location_id",
        "item_id",
        "qty_on_hand_cases",
        "code_date",
        "last_transaction_id",
        "source_code",
    },
}

_FORBIDDEN_COLUMNS = {
    "scenario_name",
    "scenario_version",
    "pattern_name",
    "equipment_area",
    "capacity_cases",
    "handling_unit_id",
    "pallet_id",
    "is_injected_anomaly",
    "true_root_cause",
    "physical_quantity",
}


def validate_wms_dataset(
    connection: sqlite3.Connection, *, allow_sandbox: bool = False
) -> ValidationResult:
    """Validate schema, master files, live inventory, audit, and snapshots."""

    repository = WmsFoundationRepository(connection)
    failures: list[ValidationIssue] = []
    failures.extend(_validate_schema(repository, allow_sandbox=allow_sandbox))
    if failures:
        return ValidationResult(tuple(failures))
    failures.extend(_validate_metadata(repository))
    failures.extend(_validate_foreign_keys(repository))
    failures.extend(_validate_item_master(connection))
    failures.extend(_validate_location_master(connection))
    failures.extend(_validate_inventory_master(connection))
    failures.extend(_validate_inventory_transactions(connection))
    failures.extend(_validate_opening_snapshot(connection))
    return ValidationResult(tuple(failures))


def _validate_schema(
    repository: WmsFoundationRepository, *, allow_sandbox: bool
) -> list[ValidationIssue]:
    failures: list[ValidationIssue] = []
    missing_tables = sorted(set(WMS_TABLES) - repository.table_names())
    if missing_tables:
        return [
            ValidationIssue("schema", f"Missing required table(s): {', '.join(missing_tables)}")
        ]
    missing_views = sorted(set(WMS_REPORT_VIEWS) - repository.view_names())
    if missing_views:
        failures.append(
            ValidationIssue(
                "schema", f"Missing required WMS report view(s): {', '.join(missing_views)}"
            )
        )
    supported_versions = {3, 4} if allow_sandbox else {3}
    if repository.user_version() not in supported_versions:
        failures.append(
            ValidationIssue(
                "schema", f"Unsupported SQLite user_version: {repository.user_version()}"
            )
        )
    if repository.schema_versions() != [WMS_SCHEMA_VERSION]:
        failures.append(ValidationIssue("schema", "Schema metadata is not version 3.0.0"))
    for table_name, required in _REQUIRED_COLUMNS.items():
        columns = repository.table_columns(table_name)
        missing = sorted(required - columns)
        if missing:
            failures.append(
                ValidationIssue(
                    "schema",
                    f"{table_name} missing required column(s): {', '.join(missing)}",
                )
            )
    for table_name in WMS_TABLES:
        forbidden = sorted(repository.table_columns(table_name) & _FORBIDDEN_COLUMNS)
        if forbidden:
            failures.append(
                ValidationIssue(
                    "schema",
                    f"{table_name} contains prohibited column(s): {', '.join(forbidden)}",
                )
            )
    return failures


def _validate_metadata(repository: WmsFoundationRepository) -> list[ValidationIssue]:
    try:
        metadata = repository.run_metadata()
    except sqlite3.DatabaseError as exc:
        return [ValidationIssue("metadata", str(exc))]
    failures: list[ValidationIssue] = []
    if metadata.schema_version != WMS_SCHEMA_VERSION:
        failures.append(ValidationIssue("metadata", "Run schema_version is not 3.0.0"))
    if metadata.simulation_start_utc >= metadata.simulation_end_utc:
        failures.append(
            ValidationIssue("metadata", "simulation_start_utc must precede simulation_end_utc")
        )
    return failures


def _validate_foreign_keys(repository: WmsFoundationRepository) -> list[ValidationIssue]:
    violations = repository.foreign_key_violations()
    if not violations:
        return []
    return [ValidationIssue("foreign_keys", f"Foreign-key violation(s): {len(violations)}")]


def _validate_item_master(connection: sqlite3.Connection) -> list[ValidationIssue]:
    failures: list[ValidationIssue] = []
    rows = connection.execute(
        """
        SELECT item_id, case_length_in, case_width_in, case_height_in, case_cube_ft3,
            cases_per_layer, layers_per_pallet, cases_per_pallet
        FROM item_master
        """
    ).fetchall()
    for row in rows:
        expected_cube = round(float(row[1]) * float(row[2]) * float(row[3]) / 1728.0, 6)
        if not isclose(float(row[4]), expected_cube, rel_tol=0.0, abs_tol=1e-6):
            failures.append(ValidationIssue("item_master", f"{row[0]} has inconsistent case cube"))
        if int(row[7]) != int(row[5]) * int(row[6]):
            failures.append(
                ValidationIssue("item_master", f"{row[0]} has inconsistent pallet pattern")
            )
    return failures


def _validate_location_master(connection: sqlite3.Connection) -> list[ValidationIssue]:
    count = int(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM location_master
            WHERE (location_type = 'PICK' AND (pickable_flag != 1 OR active_flag != 1))
                OR (location_type != 'PICK' AND pickable_flag != 0)
                OR (location_type IN ('PICK', 'RESERVE') AND pallet_capacity IS NULL)
            """
        ).fetchone()[0]
    )
    if count:
        return [ValidationIssue("location_master", f"Invalid location profile rows: {count}")]
    return []


def _validate_inventory_master(connection: sqlite3.Connection) -> list[ValidationIssue]:
    checks = {
        "Every location must have exactly one inventory row": """
            SELECT COUNT(*) FROM location_master AS l
            LEFT JOIN inventory_master AS i
                ON i.run_id = l.run_id AND i.location_id = l.location_id
            WHERE i.location_id IS NULL
        """,
        "Inventory rows must reference an existing location": """
            SELECT COUNT(*) FROM inventory_master AS i
            LEFT JOIN location_master AS l
                ON l.run_id = i.run_id AND l.location_id = i.location_id
            WHERE l.location_id IS NULL
        """,
        "Occupied inventory must have a code date": """
            SELECT COUNT(*) FROM inventory_master
            WHERE qty_on_hand_cases > 0 AND code_date IS NULL
        """,
        "Inventory item zone must match location zone": """
            SELECT COUNT(*)
            FROM inventory_master AS i
            JOIN item_master AS item
                ON item.run_id = i.run_id AND item.item_id = i.item_id
            JOIN location_master AS l
                ON l.run_id = i.run_id AND l.location_id = i.location_id
            JOIN zone AS z ON z.run_id = l.run_id AND z.zone_id = l.zone_id
            WHERE item.required_zone_code != z.zone_code
        """,
        "Pick locations require assignment and replenishment controls": """
            SELECT COUNT(*)
            FROM inventory_master AS i
            JOIN location_master AS l
                ON l.run_id = i.run_id AND l.location_id = i.location_id
            WHERE l.location_type = 'PICK'
                AND (i.item_id IS NULL OR i.reorder_trigger_cases IS NULL
                    OR i.minimum_qty_cases IS NULL OR i.target_qty_cases IS NULL
                    OR i.maximum_qty_cases IS NULL)
        """,
        "Non-pick locations cannot have replenishment controls": """
            SELECT COUNT(*)
            FROM inventory_master AS i
            JOIN location_master AS l
                ON l.run_id = i.run_id AND l.location_id = i.location_id
            WHERE l.location_type != 'PICK'
                AND (i.reorder_trigger_cases IS NOT NULL OR i.minimum_qty_cases IS NOT NULL
                    OR i.target_qty_cases IS NOT NULL OR i.maximum_qty_cases IS NOT NULL)
        """,
        "Pick maximum cannot exceed dynamic physical capacity": """
            SELECT COUNT(*)
            FROM inventory_master AS i
            JOIN location_master AS l
                ON l.run_id = i.run_id AND l.location_id = i.location_id
            JOIN item_master AS item
                ON item.run_id = i.run_id AND item.item_id = i.item_id
            WHERE l.location_type = 'PICK'
                AND i.maximum_qty_cases > l.pallet_capacity * item.cases_per_pallet
        """,
        "Inactive and non-inventory locations must remain empty": """
            SELECT COUNT(*)
            FROM inventory_master AS i
            JOIN location_master AS l
                ON l.run_id = i.run_id AND l.location_id = i.location_id
            WHERE (l.active_flag = 0 OR l.location_type IN ('DOCK', 'INACTIVE'))
                AND (i.item_id IS NOT NULL OR i.qty_on_hand_cases != 0 OR i.code_date IS NOT NULL)
        """,
    }
    return _count_issues(connection, "inventory_master", checks)


def _validate_inventory_transactions(connection: sqlite3.Connection) -> list[ValidationIssue]:
    checks = {
        "Inventory transaction balance arithmetic must reconcile": """
            SELECT COUNT(*) FROM inventory_transaction
            WHERE balance_after_cases != balance_before_cases + qty_delta_cases
        """,
        "Inventory transaction ordering must be unique": """
            SELECT COUNT(*) FROM (
                SELECT run_id, event_sequence, line_number, COUNT(*) AS row_count
                FROM inventory_transaction
                GROUP BY run_id, event_sequence, line_number
                HAVING row_count > 1
            )
        """,
        "Transaction balances must follow opening inventory and prior audit rows": """
            WITH ordered AS (
                SELECT
                    transaction_id,
                    balance_before_cases,
                    COALESCE(opening.qty_on_hand_cases, 0) + COALESCE(
                        SUM(qty_delta_cases) OVER (
                            PARTITION BY tx.run_id, tx.location_id
                            ORDER BY event_sequence, line_number
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                        ),
                        0
                    ) AS expected_before
                FROM inventory_transaction AS tx
                LEFT JOIN inventory_snapshot AS opening
                    ON opening.run_id = tx.run_id
                    AND opening.location_id = tx.location_id
                    AND opening.snapshot_type = 'OPENING_SYSTEM'
            )
            SELECT COUNT(*) FROM ordered
            WHERE balance_before_cases != expected_before
        """,
        "Transfer transaction groups must contain balanced signed pairs": """
            SELECT COUNT(*) FROM (
                SELECT run_id, transaction_group_id
                FROM inventory_transaction
                WHERE transaction_type IN ('TRANSFER_OUT', 'TRANSFER_IN')
                GROUP BY run_id, transaction_group_id
                HAVING COUNT(*) != 2 OR SUM(qty_delta_cases) != 0
            )
        """,
        "Inventory transactions must reference accepted commands": """
            SELECT COUNT(*)
            FROM inventory_transaction AS tx
            LEFT JOIN wms_command AS command
                ON command.run_id = tx.run_id AND command.command_id = tx.command_id
            WHERE command.command_id IS NULL
        """,
    }
    return _count_issues(connection, "inventory_transaction", checks)


def _validate_opening_snapshot(connection: sqlite3.Connection) -> list[ValidationIssue]:
    checks = {
        "Opening snapshot must contain one line per location": """
            SELECT ABS(
                (SELECT COUNT(*) FROM location_master)
                - (SELECT COUNT(*) FROM inventory_snapshot WHERE snapshot_type = 'OPENING_SYSTEM')
            )
        """,
        "Opening snapshot plus audit replay must equal live inventory": """
            WITH movement AS (
                SELECT run_id, location_id, SUM(qty_delta_cases) AS qty_delta_cases
                FROM inventory_transaction
                GROUP BY run_id, location_id
            )
            SELECT COUNT(*)
            FROM inventory_master AS live
            LEFT JOIN inventory_snapshot AS opening
                ON opening.run_id = live.run_id
                AND opening.location_id = live.location_id
                AND opening.snapshot_type = 'OPENING_SYSTEM'
            LEFT JOIN movement
                ON movement.run_id = live.run_id
                AND movement.location_id = live.location_id
            WHERE opening.snapshot_line_id IS NULL
                OR live.qty_on_hand_cases
                    != opening.qty_on_hand_cases + COALESCE(movement.qty_delta_cases, 0)
        """,
    }
    return _count_issues(connection, "inventory_snapshot", checks)


def _count_issues(
    connection: sqlite3.Connection,
    category: str,
    checks: dict[str, str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for message, query in checks.items():
        count = int(connection.execute(query).fetchone()[0])
        if count:
            issues.append(ValidationIssue(category, f"{message}: {count} row(s)"))
    return issues
