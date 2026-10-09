"""Narrow additive schema for verified release-0.2.0 sandboxes."""

from __future__ import annotations

SANDBOX_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE sandbox_identity (
        sandbox_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL UNIQUE,
        manifest_version TEXT NOT NULL,
        source_database_path TEXT NOT NULL,
        source_database_sha256 TEXT NOT NULL CHECK(length(source_database_sha256) = 64),
        source_schema_version TEXT NOT NULL CHECK(source_schema_version = '3.0.0'),
        sandbox_schema_version TEXT NOT NULL CHECK(sandbox_schema_version = '3.1.0'),
        created_at_utc TEXT NOT NULL,
        created_by_application_version TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES simulation_run(run_id)
    )
    """,
    """
    CREATE TABLE maintenance_batch (
        run_id TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        sandbox_id TEXT NOT NULL,
        workflow_type TEXT NOT NULL CHECK(
            workflow_type IN ('INVENTORY_ADJUSTMENTS', 'REPLENISHMENT_CONTROLS')
        ),
        canonical_payload_sha256 TEXT NOT NULL,
        normalized_input_sha256 TEXT NOT NULL,
        preview_manifest_sha256 TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status = 'APPLIED'),
        applied_at_utc TEXT NOT NULL,
        applied_by_application_version TEXT NOT NULL,
        post_snapshot_batch_id TEXT,
        PRIMARY KEY (run_id, batch_id),
        FOREIGN KEY (run_id) REFERENCES simulation_run(run_id),
        FOREIGN KEY (sandbox_id) REFERENCES sandbox_identity(sandbox_id)
    )
    """,
    """
    CREATE TABLE maintenance_batch_row (
        run_id TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        row_reference TEXT NOT NULL,
        command_id TEXT NOT NULL,
        result_record_type TEXT NOT NULL,
        result_record_id TEXT NOT NULL,
        transaction_id TEXT,
        status TEXT NOT NULL CHECK(status = 'APPLIED'),
        message TEXT NOT NULL,
        PRIMARY KEY (run_id, batch_id, row_reference),
        UNIQUE (run_id, command_id),
        FOREIGN KEY (run_id, batch_id) REFERENCES maintenance_batch(run_id, batch_id),
        FOREIGN KEY (run_id, command_id) REFERENCES wms_command(run_id, command_id)
    )
    """,
    """
    CREATE TABLE replenishment_control_change (
        run_id TEXT NOT NULL,
        control_change_id TEXT NOT NULL,
        command_id TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        row_reference TEXT NOT NULL,
        location_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        operator_id TEXT NOT NULL,
        old_minimum_qty_cases INTEGER NOT NULL,
        old_reorder_trigger_cases INTEGER NOT NULL,
        old_target_qty_cases INTEGER NOT NULL,
        old_maximum_qty_cases INTEGER NOT NULL,
        new_minimum_qty_cases INTEGER NOT NULL,
        new_reorder_trigger_cases INTEGER NOT NULL,
        new_target_qty_cases INTEGER NOT NULL,
        new_maximum_qty_cases INTEGER NOT NULL,
        event_utc TEXT NOT NULL,
        recorded_utc TEXT NOT NULL,
        application_version TEXT NOT NULL,
        user_note TEXT NOT NULL,
        source_preview_reference TEXT NOT NULL,
        PRIMARY KEY (run_id, control_change_id),
        UNIQUE (run_id, command_id),
        FOREIGN KEY (run_id, command_id) REFERENCES wms_command(run_id, command_id),
        FOREIGN KEY (run_id, batch_id, row_reference)
            REFERENCES maintenance_batch_row(run_id, batch_id, row_reference),
        FOREIGN KEY (run_id, location_id) REFERENCES location_master(run_id, location_id),
        FOREIGN KEY (run_id, item_id) REFERENCES item_master(run_id, item_id),
        FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id),
        CHECK (event_utc <= recorded_utc)
    )
    """,
    """
    CREATE TRIGGER sandbox_identity_no_update
    BEFORE UPDATE ON sandbox_identity
    BEGIN SELECT RAISE(ABORT, 'sandbox_identity is immutable'); END
    """,
    """
    CREATE TRIGGER sandbox_identity_no_delete
    BEFORE DELETE ON sandbox_identity
    BEGIN SELECT RAISE(ABORT, 'sandbox_identity is immutable'); END
    """,
    """
    CREATE TRIGGER maintenance_batch_no_update
    BEFORE UPDATE ON maintenance_batch
    BEGIN SELECT RAISE(ABORT, 'maintenance_batch is immutable'); END
    """,
    """
    CREATE TRIGGER maintenance_batch_no_delete
    BEFORE DELETE ON maintenance_batch
    BEGIN SELECT RAISE(ABORT, 'maintenance_batch is immutable'); END
    """,
    """
    CREATE TRIGGER maintenance_batch_row_no_update
    BEFORE UPDATE ON maintenance_batch_row
    BEGIN SELECT RAISE(ABORT, 'maintenance_batch_row is immutable'); END
    """,
    """
    CREATE TRIGGER maintenance_batch_row_no_delete
    BEFORE DELETE ON maintenance_batch_row
    BEGIN SELECT RAISE(ABORT, 'maintenance_batch_row is immutable'); END
    """,
    """
    CREATE TRIGGER replenishment_control_change_no_update
    BEFORE UPDATE ON replenishment_control_change
    BEGIN SELECT RAISE(ABORT, 'replenishment_control_change is immutable'); END
    """,
    """
    CREATE TRIGGER replenishment_control_change_no_delete
    BEFORE DELETE ON replenishment_control_change
    BEGIN SELECT RAISE(ABORT, 'replenishment_control_change is immutable'); END
    """,
)

SANDBOX_TABLES = (
    "sandbox_identity",
    "maintenance_batch",
    "maintenance_batch_row",
    "replenishment_control_change",
)
