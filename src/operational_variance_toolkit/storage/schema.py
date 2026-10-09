from __future__ import annotations

SCHEMA_VERSION = "1.0.0"
PHASE2_SCHEMA_VERSION = "2.0.0"
WMS_SCHEMA_VERSION = "3.0.0"

SCHEMA_SQL = """
CREATE TABLE schema_metadata (
    schema_version TEXT PRIMARY KEY,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE simulation_run (
    run_id TEXT PRIMARY KEY,
    scenario_name TEXT NOT NULL,
    scenario_version TEXT NOT NULL,
    seed INTEGER NOT NULL CHECK (seed >= 0),
    schema_version TEXT NOT NULL,
    generator_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    facility_timezone TEXT NOT NULL,
    simulation_start_utc TEXT NOT NULL,
    simulation_end_utc TEXT NOT NULL,
    generated_at_utc TEXT NOT NULL
);

CREATE TABLE facility (
    run_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    facility_name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    PRIMARY KEY (run_id, facility_id),
    FOREIGN KEY (run_id) REFERENCES simulation_run(run_id) ON DELETE CASCADE
);

CREATE TABLE zone (
    run_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    zone_code TEXT NOT NULL CHECK (zone_code IN ('FROZEN', 'CHILLED', 'AMBIENT')),
    min_temp_f REAL,
    max_temp_f REAL,
    active_flag INTEGER NOT NULL CHECK (active_flag IN (0, 1)),
    PRIMARY KEY (run_id, zone_id),
    FOREIGN KEY (run_id, facility_id) REFERENCES facility(run_id, facility_id) ON DELETE CASCADE
);

CREATE TABLE location (
    run_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    location_type TEXT NOT NULL CHECK (
        location_type IN ('PICK', 'RESERVE', 'STAGING', 'QA_HOLD', 'DOCK', 'INACTIVE')
    ),
    aisle_code TEXT,
    bay_number INTEGER,
    level_number INTEGER,
    position_number INTEGER,
    equipment_area TEXT,
    capacity_cases INTEGER,
    capacity_pallets INTEGER,
    pickable_flag INTEGER NOT NULL CHECK (pickable_flag IN (0, 1)),
    active_flag INTEGER NOT NULL CHECK (active_flag IN (0, 1)),
    PRIMARY KEY (run_id, location_id),
    FOREIGN KEY (run_id, zone_id) REFERENCES zone(run_id, zone_id) ON DELETE CASCADE
);

CREATE TABLE item (
    run_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    item_description TEXT NOT NULL,
    category TEXT NOT NULL,
    required_zone_code TEXT NOT NULL,
    cases_per_pallet INTEGER NOT NULL CHECK (cases_per_pallet > 0),
    case_weight_lb REAL NOT NULL CHECK (case_weight_lb > 0),
    case_cube_ft3 REAL NOT NULL CHECK (case_cube_ft3 > 0),
    fragility_score REAL NOT NULL CHECK (fragility_score BETWEEN 0 AND 1),
    shelf_life_days INTEGER,
    velocity_class TEXT NOT NULL CHECK (velocity_class IN ('A', 'B', 'C')),
    expected_cases_per_day REAL NOT NULL CHECK (expected_cases_per_day > 0),
    active_flag INTEGER NOT NULL CHECK (active_flag IN (0, 1)),
    PRIMARY KEY (run_id, item_id),
    FOREIGN KEY (run_id) REFERENCES simulation_run(run_id) ON DELETE CASCADE
);

CREATE TABLE operator (
    run_id TEXT NOT NULL,
    operator_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (
        role IN ('SELECTOR', 'REPLENISHMENT', 'QA', 'INVENTORY_CONTROL', 'SYSTEM')
    ),
    home_zone_id TEXT,
    shift_code TEXT NOT NULL,
    experience_months INTEGER NOT NULL CHECK (experience_months >= 0),
    active_flag INTEGER NOT NULL CHECK (active_flag IN (0, 1)),
    PRIMARY KEY (run_id, operator_id),
    FOREIGN KEY (run_id) REFERENCES simulation_run(run_id) ON DELETE CASCADE
);

CREATE TABLE shift (
    run_id TEXT NOT NULL,
    shift_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    shift_code TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    operating_date_local TEXT NOT NULL,
    PRIMARY KEY (run_id, shift_id),
    FOREIGN KEY (run_id, facility_id) REFERENCES facility(run_id, facility_id) ON DELETE CASCADE
);

CREATE TABLE slot_assignment (
    run_id TEXT NOT NULL,
    assignment_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    pick_location_id TEXT NOT NULL,
    effective_start_utc TEXT NOT NULL,
    effective_end_utc TEXT,
    reorder_trigger_cases INTEGER NOT NULL CHECK (reorder_trigger_cases >= 0),
    target_cases INTEGER NOT NULL CHECK (target_cases > 0),
    minimum_cases INTEGER NOT NULL CHECK (minimum_cases >= 0),
    maximum_cases INTEGER NOT NULL CHECK (maximum_cases >= 0),
    priority_rank INTEGER NOT NULL CHECK (priority_rank > 0),
    FOREIGN KEY (run_id, item_id) REFERENCES item(run_id, item_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, pick_location_id) REFERENCES location(run_id, location_id)
        ON DELETE CASCADE
);

CREATE TABLE work_assignment (
    run_id TEXT NOT NULL,
    work_assignment_id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL,
    shift_id TEXT NOT NULL,
    role TEXT NOT NULL,
    zone_id TEXT,
    FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, shift_id) REFERENCES shift(run_id, shift_id) ON DELETE CASCADE
);

CREATE TABLE handling_unit (
    run_id TEXT NOT NULL,
    handling_unit_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    lot_code TEXT,
    expiration_date TEXT,
    initial_qty_cases INTEGER NOT NULL CHECK (initial_qty_cases > 0),
    status TEXT NOT NULL CHECK (status IN ('AVAILABLE', 'HOLD', 'DEPLETED', 'DISPOSED')),
    PRIMARY KEY (run_id, handling_unit_id),
    FOREIGN KEY (run_id, item_id) REFERENCES item(run_id, item_id) ON DELETE CASCADE
);

CREATE TABLE inventory_snapshot (
    run_id TEXT NOT NULL,
    snapshot_id TEXT PRIMARY KEY,
    snapshot_utc TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    location_id TEXT,
    handling_unit_id TEXT,
    qty_cases INTEGER NOT NULL CHECK (qty_cases >= 0),
    source_code TEXT NOT NULL,
    FOREIGN KEY (run_id, item_id) REFERENCES item(run_id, item_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, location_id) REFERENCES location(run_id, location_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, handling_unit_id) REFERENCES handling_unit(run_id, handling_unit_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_zone_facility ON zone(run_id, facility_id);
CREATE INDEX idx_location_zone ON location(run_id, zone_id);
CREATE INDEX idx_slot_item ON slot_assignment(run_id, item_id);
CREATE INDEX idx_slot_location ON slot_assignment(run_id, pick_location_id);
CREATE INDEX idx_inventory_item ON inventory_snapshot(run_id, item_id);
"""

PHASE2_TRANSACTION_SQL = """
CREATE TABLE event_sequence_registry (
    run_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL CHECK (event_sequence > 0),
    event_type TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_id TEXT NOT NULL,
    event_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, event_sequence),
    UNIQUE (run_id, source_table, source_id),
    FOREIGN KEY (run_id) REFERENCES simulation_run(run_id) ON DELETE CASCADE
);

CREATE TABLE trip (
    run_id TEXT NOT NULL,
    trip_id TEXT NOT NULL,
    shift_id TEXT NOT NULL,
    selector_id TEXT NOT NULL,
    assigned_zone_id TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    continuation_flag INTEGER NOT NULL CHECK (continuation_flag IN (0, 1)),
    planned_pick_lines INTEGER NOT NULL CHECK (planned_pick_lines > 0),
    planned_cases INTEGER NOT NULL CHECK (planned_cases > 0),
    PRIMARY KEY (run_id, trip_id),
    FOREIGN KEY (run_id, shift_id) REFERENCES shift(run_id, shift_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, selector_id) REFERENCES operator(run_id, operator_id)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, assigned_zone_id) REFERENCES zone(run_id, zone_id)
        ON DELETE CASCADE,
    CHECK (start_utc < end_utc)
);

CREATE TABLE pick_event (
    run_id TEXT NOT NULL,
    pick_event_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    trip_id TEXT NOT NULL,
    selector_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    pick_location_id TEXT NOT NULL,
    event_utc TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    requested_qty_cases INTEGER NOT NULL CHECK (requested_qty_cases > 0),
    picked_qty_cases INTEGER NOT NULL CHECK (picked_qty_cases >= 0),
    short_qty_cases INTEGER NOT NULL CHECK (short_qty_cases >= 0),
    short_reason_code TEXT,
    system_qty_before_cases INTEGER NOT NULL CHECK (system_qty_before_cases >= 0),
    system_qty_after_cases INTEGER NOT NULL CHECK (system_qty_after_cases >= 0),
    eligible_pick_flag INTEGER NOT NULL CHECK (eligible_pick_flag IN (0, 1)),
    PRIMARY KEY (run_id, pick_event_id),
    UNIQUE (run_id, event_sequence),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, trip_id) REFERENCES trip(run_id, trip_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, selector_id) REFERENCES operator(run_id, operator_id)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, item_id) REFERENCES item(run_id, item_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, pick_location_id) REFERENCES location(run_id, location_id)
        ON DELETE CASCADE,
    CHECK (picked_qty_cases + short_qty_cases = requested_qty_cases),
    CHECK (system_qty_after_cases = system_qty_before_cases - picked_qty_cases),
    CHECK ((short_qty_cases = 0 AND short_reason_code IS NULL) OR
           (short_qty_cases > 0 AND short_reason_code IS NOT NULL)),
    CHECK (recorded_utc >= event_utc)
);

CREATE TABLE replenishment_task (
    run_id TEXT NOT NULL,
    replenishment_task_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    source_location_id TEXT NOT NULL,
    destination_location_id TEXT NOT NULL,
    operator_id TEXT,
    created_utc TEXT NOT NULL,
    started_utc TEXT,
    confirmed_utc TEXT,
    recorded_utc TEXT NOT NULL,
    requested_qty_cases INTEGER NOT NULL CHECK (requested_qty_cases > 0),
    confirmed_qty_cases INTEGER NOT NULL CHECK (confirmed_qty_cases >= 0),
    status TEXT NOT NULL CHECK (status IN ('CREATED', 'STARTED', 'CONFIRMED', 'CANCELED')),
    delay_reason_code TEXT,
    PRIMARY KEY (run_id, replenishment_task_id),
    UNIQUE (run_id, event_sequence),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, item_id) REFERENCES item(run_id, item_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, source_location_id) REFERENCES location(run_id, location_id)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, destination_location_id) REFERENCES location(run_id, location_id)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id)
        ON DELETE CASCADE,
    CHECK (recorded_utc >= created_utc),
    CHECK (started_utc IS NULL OR started_utc >= created_utc),
    CHECK (confirmed_utc IS NULL OR started_utc IS NOT NULL),
    CHECK (confirmed_utc IS NULL OR confirmed_utc >= started_utc),
    CHECK ((status = 'CONFIRMED' AND confirmed_utc IS NOT NULL AND confirmed_qty_cases > 0)
        OR (status != 'CONFIRMED'))
);

CREATE TABLE qa_event (
    run_id TEXT NOT NULL,
    qa_event_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    handling_unit_id TEXT,
    operator_id TEXT,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('INSPECTION', 'DAMAGE_FOUND', 'HOLD_PLACED', 'RELEASED')
    ),
    occurred_utc TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    qty_affected_cases INTEGER NOT NULL CHECK (qty_affected_cases > 0),
    reason_code TEXT NOT NULL,
    disposition_code TEXT NOT NULL CHECK (
        disposition_code IN ('NO_ACTION', 'HOLD', 'RESTACK', 'RETURN_TO_STOCK', 'DISPOSE')
    ),
    PRIMARY KEY (run_id, qa_event_id),
    UNIQUE (run_id, event_sequence),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, item_id) REFERENCES item(run_id, item_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, location_id) REFERENCES location(run_id, location_id)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, handling_unit_id) REFERENCES handling_unit(run_id, handling_unit_id)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id)
        ON DELETE CASCADE,
    CHECK (recorded_utc >= occurred_utc)
);

CREATE TABLE inventory_adjustment (
    run_id TEXT NOT NULL,
    adjustment_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    operator_id TEXT,
    effective_utc TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    qty_delta_cases INTEGER NOT NULL CHECK (qty_delta_cases != 0),
    reason_code TEXT NOT NULL CHECK (
        reason_code IN ('DAMAGE_DISPOSAL', 'COUNT_CORRECTION', 'FOUND_PRODUCT')
    ),
    reference_code TEXT,
    PRIMARY KEY (run_id, adjustment_id),
    UNIQUE (run_id, event_sequence),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, item_id) REFERENCES item(run_id, item_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, location_id) REFERENCES location(run_id, location_id)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id)
        ON DELETE CASCADE,
    CHECK (recorded_utc >= effective_utc)
);

CREATE TABLE system_event (
    run_id TEXT NOT NULL,
    system_event_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('RF_DELAY', 'EQUIPMENT_DELAY', 'WMS_MAINTENANCE')
    ),
    zone_id TEXT,
    location_id TEXT,
    equipment_area TEXT,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    severity_code TEXT NOT NULL CHECK (severity_code IN ('LOW', 'MEDIUM', 'HIGH')),
    recorded_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, system_event_id),
    UNIQUE (run_id, event_sequence),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, zone_id) REFERENCES zone(run_id, zone_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, location_id) REFERENCES location(run_id, location_id)
        ON DELETE CASCADE,
    CHECK (start_utc < end_utc),
    CHECK (recorded_utc >= start_utc),
    CHECK (zone_id IS NOT NULL OR location_id IS NOT NULL OR equipment_area IS NOT NULL)
);

CREATE INDEX idx_event_registry_time ON event_sequence_registry(run_id, event_utc, event_sequence);
CREATE INDEX idx_trip_shift ON trip(run_id, shift_id, start_utc);
CREATE INDEX idx_pick_trip_sequence ON pick_event(run_id, trip_id, event_sequence);
CREATE INDEX idx_pick_item_location_time ON pick_event(
    run_id, item_id, pick_location_id, event_utc
);
CREATE INDEX idx_replenishment_item_time ON replenishment_task(
    run_id, item_id, confirmed_utc
);
CREATE INDEX idx_qa_event_type_time ON qa_event(run_id, event_type, occurred_utc);
CREATE INDEX idx_adjustment_item_time ON inventory_adjustment(run_id, item_id, effective_utc);
CREATE INDEX idx_system_event_time ON system_event(run_id, start_utc, end_utc);
"""

PHASE2_SCHEMA_SQL = f"{SCHEMA_SQL}\n{PHASE2_TRANSACTION_SQL}"

WMS_SCHEMA_SQL = """
CREATE TABLE schema_metadata (
    schema_version TEXT PRIMARY KEY CHECK (schema_version = '3.0.0'),
    sqlite_user_version INTEGER NOT NULL CHECK (sqlite_user_version = 3),
    created_at_utc TEXT NOT NULL
);

CREATE TABLE simulation_run (
    run_id TEXT PRIMARY KEY,
    seed INTEGER NOT NULL CHECK (seed >= 0),
    schema_version TEXT NOT NULL CHECK (schema_version = '3.0.0'),
    generator_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    facility_timezone TEXT NOT NULL,
    simulation_start_utc TEXT NOT NULL,
    simulation_end_utc TEXT NOT NULL,
    generated_at_utc TEXT NOT NULL,
    CHECK (simulation_start_utc < simulation_end_utc)
);

CREATE TABLE facility (
    run_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    facility_name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    PRIMARY KEY (run_id, facility_id),
    FOREIGN KEY (run_id) REFERENCES simulation_run(run_id) ON DELETE CASCADE
);

CREATE TABLE zone (
    run_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    zone_code TEXT NOT NULL CHECK (zone_code IN ('FROZEN', 'CHILLED', 'AMBIENT')),
    min_temp_f REAL,
    max_temp_f REAL,
    active_flag INTEGER NOT NULL CHECK (active_flag IN (0, 1)),
    PRIMARY KEY (run_id, zone_id),
    UNIQUE (run_id, zone_code),
    FOREIGN KEY (run_id, facility_id) REFERENCES facility(run_id, facility_id)
        ON DELETE CASCADE,
    CHECK (min_temp_f IS NULL OR max_temp_f IS NULL OR min_temp_f <= max_temp_f)
);

CREATE TABLE item_master (
    run_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    item_description TEXT NOT NULL,
    category TEXT NOT NULL,
    required_zone_code TEXT NOT NULL CHECK (
        required_zone_code IN ('FROZEN', 'CHILLED', 'AMBIENT')
    ),
    case_length_in REAL NOT NULL CHECK (case_length_in > 0),
    case_width_in REAL NOT NULL CHECK (case_width_in > 0),
    case_height_in REAL NOT NULL CHECK (case_height_in > 0),
    case_cube_ft3 REAL NOT NULL CHECK (case_cube_ft3 > 0),
    case_weight_lb REAL NOT NULL CHECK (case_weight_lb > 0),
    cases_per_layer INTEGER NOT NULL CHECK (cases_per_layer > 0),
    layers_per_pallet INTEGER NOT NULL CHECK (layers_per_pallet > 0),
    cases_per_pallet INTEGER NOT NULL CHECK (cases_per_pallet > 0),
    fragility_score REAL NOT NULL CHECK (fragility_score BETWEEN 0 AND 1),
    shelf_life_days INTEGER CHECK (shelf_life_days IS NULL OR shelf_life_days > 0),
    velocity_class TEXT NOT NULL CHECK (velocity_class IN ('A', 'B', 'C')),
    expected_cases_per_day REAL NOT NULL CHECK (expected_cases_per_day > 0),
    active_flag INTEGER NOT NULL CHECK (active_flag IN (0, 1)),
    PRIMARY KEY (run_id, item_id),
    FOREIGN KEY (run_id) REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    CHECK (cases_per_pallet = cases_per_layer * layers_per_pallet)
);

CREATE TABLE location_master (
    run_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    location_type TEXT NOT NULL CHECK (
        location_type IN ('PICK', 'RESERVE', 'STAGING', 'QA_HOLD', 'DOCK', 'INACTIVE')
    ),
    aisle_code TEXT,
    bay_number INTEGER CHECK (bay_number IS NULL OR bay_number > 0),
    level_number INTEGER CHECK (level_number IS NULL OR level_number >= 0),
    position_number INTEGER CHECK (position_number IS NULL OR position_number > 0),
    pallet_capacity INTEGER CHECK (pallet_capacity IS NULL OR pallet_capacity > 0),
    pickable_flag INTEGER NOT NULL CHECK (pickable_flag IN (0, 1)),
    active_flag INTEGER NOT NULL CHECK (active_flag IN (0, 1)),
    PRIMARY KEY (run_id, location_id),
    FOREIGN KEY (run_id, zone_id) REFERENCES zone(run_id, zone_id) ON DELETE CASCADE,
    CHECK (
        (location_type = 'PICK' AND aisle_code IS NOT NULL AND bay_number IS NOT NULL
            AND pallet_capacity IS NOT NULL AND pickable_flag = 1 AND active_flag = 1)
        OR (location_type = 'RESERVE' AND aisle_code IS NOT NULL AND bay_number IS NOT NULL
            AND pallet_capacity IS NOT NULL AND pickable_flag = 0)
        OR (location_type NOT IN ('PICK', 'RESERVE') AND pickable_flag = 0)
    )
);

CREATE TABLE operator (
    run_id TEXT NOT NULL,
    operator_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (
        role IN ('SELECTOR', 'REPLENISHMENT', 'QA', 'INVENTORY_CONTROL', 'SYSTEM')
    ),
    home_zone_id TEXT,
    shift_code TEXT NOT NULL,
    experience_months INTEGER NOT NULL CHECK (experience_months >= 0),
    active_flag INTEGER NOT NULL CHECK (active_flag IN (0, 1)),
    PRIMARY KEY (run_id, operator_id),
    FOREIGN KEY (run_id) REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, home_zone_id) REFERENCES zone(run_id, zone_id)
);

CREATE TABLE shift (
    run_id TEXT NOT NULL,
    shift_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    shift_code TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    operating_date_local TEXT NOT NULL,
    PRIMARY KEY (run_id, shift_id),
    FOREIGN KEY (run_id, facility_id) REFERENCES facility(run_id, facility_id)
        ON DELETE CASCADE,
    CHECK (start_utc < end_utc)
);

CREATE TABLE work_assignment (
    run_id TEXT NOT NULL,
    work_assignment_id TEXT NOT NULL,
    operator_id TEXT NOT NULL,
    shift_id TEXT NOT NULL,
    role TEXT NOT NULL,
    zone_id TEXT,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, work_assignment_id),
    FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, shift_id) REFERENCES shift(run_id, shift_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, zone_id) REFERENCES zone(run_id, zone_id),
    CHECK (start_utc < end_utc)
);

CREATE TABLE event_sequence_registry (
    run_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL CHECK (event_sequence > 0),
    event_type TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    event_utc TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, event_sequence),
    UNIQUE (run_id, event_type, source_record_id),
    FOREIGN KEY (run_id) REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    CHECK (recorded_utc >= event_utc)
);

CREATE TABLE wms_command (
    run_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    command_type TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    accepted_utc TEXT NOT NULL,
    result_record_type TEXT NOT NULL,
    result_record_id TEXT NOT NULL,
    event_sequence INTEGER,
    PRIMARY KEY (run_id, command_id),
    FOREIGN KEY (run_id) REFERENCES simulation_run(run_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, event_sequence)
        REFERENCES event_sequence_registry(run_id, event_sequence)
);

CREATE TABLE inventory_transaction (
    run_id TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    transaction_group_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL CHECK (event_sequence > 0),
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    transaction_type TEXT NOT NULL CHECK (
        transaction_type IN (
            'PICK', 'TRANSFER_OUT', 'TRANSFER_IN', 'ADJUSTMENT', 'DAMAGE',
            'FOUND_PRODUCT', 'COUNT_CORRECTION', 'ASSIGNMENT', 'CLEAR_LOCATION'
        )
    ),
    location_id TEXT NOT NULL,
    related_location_id TEXT,
    item_id TEXT NOT NULL,
    qty_delta_cases INTEGER NOT NULL,
    balance_before_cases INTEGER NOT NULL CHECK (balance_before_cases >= 0),
    balance_after_cases INTEGER NOT NULL CHECK (balance_after_cases >= 0),
    operator_id TEXT,
    event_utc TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    reason_code TEXT,
    source_record_type TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    PRIMARY KEY (run_id, transaction_id),
    UNIQUE (run_id, event_sequence, line_number),
    UNIQUE (run_id, command_id, line_number),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence),
    FOREIGN KEY (run_id, location_id) REFERENCES location_master(run_id, location_id),
    FOREIGN KEY (run_id, related_location_id) REFERENCES location_master(run_id, location_id),
    FOREIGN KEY (run_id, item_id) REFERENCES item_master(run_id, item_id),
    FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id),
    CHECK (balance_after_cases = balance_before_cases + qty_delta_cases),
    CHECK (qty_delta_cases != 0 OR transaction_type IN ('ASSIGNMENT', 'CLEAR_LOCATION')),
    CHECK (recorded_utc >= event_utc)
);

CREATE TABLE inventory_master (
    run_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    item_id TEXT,
    qty_on_hand_cases INTEGER NOT NULL CHECK (qty_on_hand_cases >= 0),
    code_date TEXT,
    reorder_trigger_cases INTEGER CHECK (
        reorder_trigger_cases IS NULL OR reorder_trigger_cases >= 0
    ),
    minimum_qty_cases INTEGER CHECK (minimum_qty_cases IS NULL OR minimum_qty_cases >= 0),
    target_qty_cases INTEGER CHECK (target_qty_cases IS NULL OR target_qty_cases >= 0),
    maximum_qty_cases INTEGER CHECK (maximum_qty_cases IS NULL OR maximum_qty_cases >= 0),
    last_transaction_id TEXT,
    last_updated_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, location_id),
    FOREIGN KEY (run_id, location_id) REFERENCES location_master(run_id, location_id)
        ON DELETE CASCADE,
    FOREIGN KEY (run_id, item_id) REFERENCES item_master(run_id, item_id),
    FOREIGN KEY (run_id, last_transaction_id)
        REFERENCES inventory_transaction(run_id, transaction_id),
    CHECK (
        (item_id IS NULL AND qty_on_hand_cases = 0 AND code_date IS NULL)
        OR item_id IS NOT NULL
    ),
    CHECK (
        (reorder_trigger_cases IS NULL AND minimum_qty_cases IS NULL
            AND target_qty_cases IS NULL AND maximum_qty_cases IS NULL)
        OR (minimum_qty_cases <= reorder_trigger_cases
            AND reorder_trigger_cases <= target_qty_cases
            AND target_qty_cases <= maximum_qty_cases)
    )
);

CREATE TABLE trip (
    run_id TEXT NOT NULL,
    trip_id TEXT NOT NULL,
    shift_id TEXT NOT NULL,
    selector_id TEXT NOT NULL,
    assigned_zone_id TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    continuation_flag INTEGER NOT NULL CHECK (continuation_flag IN (0, 1)),
    planned_pick_lines INTEGER NOT NULL CHECK (planned_pick_lines > 0),
    planned_cases INTEGER NOT NULL CHECK (planned_cases > 0),
    PRIMARY KEY (run_id, trip_id),
    FOREIGN KEY (run_id, shift_id) REFERENCES shift(run_id, shift_id),
    FOREIGN KEY (run_id, selector_id) REFERENCES operator(run_id, operator_id),
    FOREIGN KEY (run_id, assigned_zone_id) REFERENCES zone(run_id, zone_id),
    CHECK (start_utc < end_utc)
);

CREATE TABLE pick_event (
    run_id TEXT NOT NULL,
    pick_event_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    trip_id TEXT NOT NULL,
    selector_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    pick_location_id TEXT NOT NULL,
    event_utc TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    requested_qty_cases INTEGER NOT NULL CHECK (requested_qty_cases > 0),
    picked_qty_cases INTEGER NOT NULL CHECK (picked_qty_cases >= 0),
    short_qty_cases INTEGER NOT NULL CHECK (short_qty_cases >= 0),
    short_reason_code TEXT,
    system_qty_before_cases INTEGER NOT NULL CHECK (system_qty_before_cases >= 0),
    system_qty_after_cases INTEGER NOT NULL CHECK (system_qty_after_cases >= 0),
    eligible_pick_flag INTEGER NOT NULL CHECK (eligible_pick_flag IN (0, 1)),
    PRIMARY KEY (run_id, pick_event_id),
    UNIQUE (run_id, command_id),
    UNIQUE (run_id, event_sequence),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence),
    FOREIGN KEY (run_id, trip_id) REFERENCES trip(run_id, trip_id),
    FOREIGN KEY (run_id, selector_id) REFERENCES operator(run_id, operator_id),
    FOREIGN KEY (run_id, item_id) REFERENCES item_master(run_id, item_id),
    FOREIGN KEY (run_id, pick_location_id) REFERENCES location_master(run_id, location_id),
    CHECK (picked_qty_cases + short_qty_cases = requested_qty_cases),
    CHECK (system_qty_after_cases = system_qty_before_cases - picked_qty_cases),
    CHECK ((short_qty_cases = 0 AND short_reason_code IS NULL)
        OR (short_qty_cases > 0 AND short_reason_code IS NOT NULL)),
    CHECK (recorded_utc >= event_utc)
);

CREATE TABLE replenishment_task (
    run_id TEXT NOT NULL,
    replenishment_task_id TEXT NOT NULL,
    create_command_id TEXT NOT NULL,
    confirm_command_id TEXT,
    event_sequence INTEGER,
    item_id TEXT NOT NULL,
    source_location_id TEXT NOT NULL,
    destination_location_id TEXT NOT NULL,
    operator_id TEXT,
    created_utc TEXT NOT NULL,
    started_utc TEXT,
    confirmed_utc TEXT,
    recorded_utc TEXT NOT NULL,
    requested_qty_cases INTEGER NOT NULL CHECK (requested_qty_cases > 0),
    confirmed_qty_cases INTEGER NOT NULL CHECK (confirmed_qty_cases >= 0),
    status TEXT NOT NULL CHECK (
        status IN ('CREATED', 'STARTED', 'CONFIRMED', 'CANCELED', 'INCOMPLETE')
    ),
    delay_reason_code TEXT,
    PRIMARY KEY (run_id, replenishment_task_id),
    UNIQUE (run_id, create_command_id),
    UNIQUE (run_id, confirm_command_id),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence),
    FOREIGN KEY (run_id, item_id) REFERENCES item_master(run_id, item_id),
    FOREIGN KEY (run_id, source_location_id) REFERENCES location_master(run_id, location_id),
    FOREIGN KEY (run_id, destination_location_id)
        REFERENCES location_master(run_id, location_id),
    FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id),
    CHECK (source_location_id != destination_location_id),
    CHECK (started_utc IS NULL OR started_utc >= created_utc),
    CHECK (confirmed_utc IS NULL OR started_utc IS NOT NULL),
    CHECK (confirmed_utc IS NULL OR confirmed_utc >= started_utc),
    CHECK ((status = 'CONFIRMED' AND confirmed_utc IS NOT NULL
        AND confirm_command_id IS NOT NULL AND event_sequence IS NOT NULL
        AND confirmed_qty_cases > 0) OR status != 'CONFIRMED')
);

CREATE TABLE qa_event (
    run_id TEXT NOT NULL,
    qa_event_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    operator_id TEXT,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'DAMAGE_FOUND', 'HOLD_PLACED', 'RESTACK', 'RELEASED',
            'DISPOSED', 'COUNT_VERIFICATION'
        )
    ),
    occurred_utc TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    qty_affected_cases INTEGER NOT NULL CHECK (qty_affected_cases > 0),
    reason_code TEXT NOT NULL,
    disposition_code TEXT NOT NULL CHECK (
        disposition_code IN (
            'NO_ACTION', 'HOLD', 'RESTACK', 'RETURN_TO_STOCK', 'DISPOSE', 'RELEASE'
        )
    ),
    PRIMARY KEY (run_id, qa_event_id),
    UNIQUE (run_id, command_id),
    UNIQUE (run_id, event_sequence),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence),
    FOREIGN KEY (run_id, item_id) REFERENCES item_master(run_id, item_id),
    FOREIGN KEY (run_id, location_id) REFERENCES location_master(run_id, location_id),
    FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id),
    CHECK (recorded_utc >= occurred_utc)
);

CREATE TABLE inventory_adjustment (
    run_id TEXT NOT NULL,
    adjustment_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    operator_id TEXT,
    effective_utc TEXT NOT NULL,
    recorded_utc TEXT NOT NULL,
    qty_delta_cases INTEGER NOT NULL CHECK (qty_delta_cases != 0),
    reason_code TEXT NOT NULL CHECK (
        reason_code IN (
            'COUNT_CORRECTION', 'DAMAGE', 'FOUND_PRODUCT', 'RECEIVING_VARIANCE',
            'TRANSACTION_CORRECTION', 'OTHER'
        )
    ),
    reference_code TEXT,
    PRIMARY KEY (run_id, adjustment_id),
    UNIQUE (run_id, command_id),
    UNIQUE (run_id, event_sequence),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence),
    FOREIGN KEY (run_id, item_id) REFERENCES item_master(run_id, item_id),
    FOREIGN KEY (run_id, location_id) REFERENCES location_master(run_id, location_id),
    FOREIGN KEY (run_id, operator_id) REFERENCES operator(run_id, operator_id),
    CHECK (recorded_utc >= effective_utc)
);

CREATE TABLE system_event (
    run_id TEXT NOT NULL,
    system_event_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'SCANNER_INTERRUPTION', 'SYSTEM_LAG', 'EQUIPMENT_DELAY',
            'BLOCKED_LOCATION', 'NETWORK_INTERRUPTION'
        )
    ),
    zone_id TEXT,
    location_id TEXT,
    aisle_code TEXT,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    severity_code TEXT NOT NULL CHECK (severity_code IN ('LOW', 'MEDIUM', 'HIGH')),
    recorded_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, system_event_id),
    UNIQUE (run_id, command_id),
    UNIQUE (run_id, event_sequence),
    FOREIGN KEY (run_id, event_sequence) REFERENCES event_sequence_registry(run_id, event_sequence),
    FOREIGN KEY (run_id, zone_id) REFERENCES zone(run_id, zone_id),
    FOREIGN KEY (run_id, location_id) REFERENCES location_master(run_id, location_id),
    CHECK (start_utc < end_utc),
    CHECK (recorded_utc >= start_utc),
    CHECK (zone_id IS NOT NULL OR location_id IS NOT NULL OR aisle_code IS NOT NULL)
);

CREATE TABLE inventory_snapshot (
    run_id TEXT NOT NULL,
    snapshot_batch_id TEXT NOT NULL,
    snapshot_line_id TEXT NOT NULL,
    snapshot_utc TEXT NOT NULL,
    snapshot_type TEXT NOT NULL CHECK (
        snapshot_type IN (
            'OPENING_SYSTEM', 'CLOSING_SYSTEM', 'SHIFT_END', 'CYCLE_COUNT', 'VERIFIED_COUNT'
        )
    ),
    location_id TEXT NOT NULL,
    item_id TEXT,
    qty_on_hand_cases INTEGER NOT NULL CHECK (qty_on_hand_cases >= 0),
    code_date TEXT,
    last_transaction_id TEXT,
    source_code TEXT NOT NULL,
    PRIMARY KEY (run_id, snapshot_line_id),
    UNIQUE (run_id, snapshot_batch_id, location_id),
    FOREIGN KEY (run_id, location_id) REFERENCES location_master(run_id, location_id),
    FOREIGN KEY (run_id, item_id) REFERENCES item_master(run_id, item_id),
    FOREIGN KEY (run_id, last_transaction_id)
        REFERENCES inventory_transaction(run_id, transaction_id),
    CHECK (
        (item_id IS NULL AND qty_on_hand_cases = 0 AND code_date IS NULL)
        OR item_id IS NOT NULL
    )
);

CREATE VIEW wms_inventory_by_location AS
SELECT
    inventory.run_id,
    location.location_id,
    zone.zone_code,
    location.location_type,
    location.aisle_code,
    location.bay_number,
    location.level_number,
    location.position_number,
    location.pallet_capacity,
    location.pickable_flag,
    location.active_flag,
    inventory.item_id,
    item.item_description,
    inventory.qty_on_hand_cases,
    inventory.code_date,
    item.cases_per_pallet,
    CASE
        WHEN inventory.item_id IS NULL OR location.pallet_capacity IS NULL THEN NULL
        ELSE location.pallet_capacity * item.cases_per_pallet
    END AS calculated_physical_maximum_cases,
    CASE
        WHEN inventory.item_id IS NULL OR location.pallet_capacity IS NULL THEN NULL
        ELSE MAX(location.pallet_capacity * item.cases_per_pallet
            - inventory.qty_on_hand_cases, 0)
    END AS available_capacity_cases,
    CASE
        WHEN inventory.item_id IS NULL OR location.pallet_capacity IS NULL THEN NULL
        ELSE ROUND(
            100.0 * inventory.qty_on_hand_cases
                / (location.pallet_capacity * item.cases_per_pallet),
            2
        )
    END AS occupancy_percentage,
    inventory.minimum_qty_cases,
    inventory.reorder_trigger_cases,
    inventory.target_qty_cases,
    inventory.maximum_qty_cases,
    inventory.last_transaction_id,
    inventory.last_updated_utc
FROM location_master AS location
JOIN zone ON zone.run_id = location.run_id AND zone.zone_id = location.zone_id
JOIN inventory_master AS inventory
    ON inventory.run_id = location.run_id AND inventory.location_id = location.location_id
LEFT JOIN item_master AS item
    ON item.run_id = inventory.run_id AND item.item_id = inventory.item_id;

CREATE VIEW wms_inventory_by_item AS
SELECT
    item.run_id,
    item.item_id,
    item.item_description,
    item.required_zone_code,
    item.velocity_class,
    COALESCE(SUM(inventory.qty_on_hand_cases), 0) AS total_on_hand_cases,
    COALESCE(SUM(CASE WHEN location.location_type = 'PICK'
        THEN inventory.qty_on_hand_cases ELSE 0 END), 0) AS pick_cases,
    COALESCE(SUM(CASE WHEN location.location_type = 'RESERVE'
        THEN inventory.qty_on_hand_cases ELSE 0 END), 0) AS reserve_cases,
    COUNT(CASE WHEN inventory.qty_on_hand_cases > 0 THEN 1 END) AS occupied_location_count,
    MIN(CASE WHEN inventory.qty_on_hand_cases > 0 THEN inventory.code_date END)
        AS earliest_code_date,
    MAX(inventory.last_updated_utc) AS latest_update_utc,
    item.cases_per_pallet,
    ROUND(COALESCE(SUM(inventory.qty_on_hand_cases), 0) * 1.0
        / item.cases_per_pallet, 3) AS pallet_equivalent_qty
FROM item_master AS item
LEFT JOIN inventory_master AS inventory
    ON inventory.run_id = item.run_id AND inventory.item_id = item.item_id
LEFT JOIN location_master AS location
    ON location.run_id = inventory.run_id AND location.location_id = inventory.location_id
GROUP BY item.run_id, item.item_id;

CREATE VIEW wms_location_profile AS
SELECT
    location.run_id,
    location.location_id,
    zone.zone_code,
    location.location_type,
    location.aisle_code,
    location.bay_number,
    location.level_number,
    location.position_number,
    location.pallet_capacity,
    location.pickable_flag,
    location.active_flag,
    inventory.item_id AS current_item_id,
    inventory.qty_on_hand_cases AS current_qty_on_hand_cases,
    CASE WHEN inventory.qty_on_hand_cases > 0 THEN 1 ELSE 0 END AS occupied_flag
FROM location_master AS location
JOIN zone ON zone.run_id = location.run_id AND zone.zone_id = location.zone_id
JOIN inventory_master AS inventory
    ON inventory.run_id = location.run_id AND inventory.location_id = location.location_id;

CREATE VIEW wms_empty_locations AS
SELECT
    run_id,
    location_id,
    zone_code,
    location_type,
    aisle_code,
    bay_number,
    level_number,
    position_number,
    pallet_capacity,
    item_id AS assigned_item_id,
    active_flag,
    pickable_flag,
    last_updated_utc
FROM wms_inventory_by_location
WHERE qty_on_hand_cases = 0;

CREATE VIEW wms_adjustment_history AS
SELECT
    adjustment.run_id,
    adjustment.adjustment_id,
    adjustment.item_id,
    adjustment.location_id,
    adjustment.qty_delta_cases,
    adjustment.reason_code,
    adjustment.operator_id,
    adjustment.effective_utc,
    adjustment.recorded_utc,
    audit.balance_before_cases,
    audit.balance_after_cases,
    adjustment.reference_code,
    audit.transaction_id,
    adjustment.command_id
FROM inventory_adjustment AS adjustment
JOIN inventory_transaction AS audit
    ON audit.run_id = adjustment.run_id AND audit.command_id = adjustment.command_id;

CREATE VIEW wms_qa_activity AS
SELECT
    run_id,
    qa_event_id,
    item_id,
    location_id,
    event_type,
    qty_affected_cases,
    operator_id,
    occurred_utc,
    recorded_utc,
    reason_code,
    disposition_code,
    command_id,
    event_sequence
FROM qa_event;

CREATE TRIGGER inventory_transaction_no_update
BEFORE UPDATE ON inventory_transaction
BEGIN
    SELECT RAISE(ABORT, 'inventory_transaction rows are immutable');
END;

CREATE TRIGGER inventory_transaction_no_delete
BEFORE DELETE ON inventory_transaction
BEGIN
    SELECT RAISE(ABORT, 'inventory_transaction rows are immutable');
END;

CREATE INDEX idx_wms_zone_facility ON zone(run_id, facility_id);
CREATE INDEX idx_wms_item_zone ON item_master(run_id, required_zone_code, item_id);
CREATE INDEX idx_wms_location_zone_type
    ON location_master(run_id, zone_id, location_type, location_id);
CREATE INDEX idx_wms_inventory_item ON inventory_master(run_id, item_id, location_id);
CREATE INDEX idx_wms_inventory_replenishment
    ON inventory_master(run_id, reorder_trigger_cases, qty_on_hand_cases);
CREATE INDEX idx_wms_transaction_sequence
    ON inventory_transaction(run_id, event_sequence, line_number);
CREATE INDEX idx_wms_command_result
    ON wms_command(run_id, result_record_type, result_record_id);
CREATE INDEX idx_wms_transaction_item_location_time
    ON inventory_transaction(run_id, item_id, location_id, event_utc);
CREATE INDEX idx_wms_snapshot_batch
    ON inventory_snapshot(run_id, snapshot_batch_id, location_id);
CREATE INDEX idx_wms_replenishment_status
    ON replenishment_task(run_id, status, created_utc);
CREATE INDEX idx_wms_pick_trip ON pick_event(run_id, trip_id, event_sequence);
"""

SCHEMA_BY_VERSION = {
    SCHEMA_VERSION: (SCHEMA_SQL, 1),
    PHASE2_SCHEMA_VERSION: (PHASE2_SCHEMA_SQL, 2),
    WMS_SCHEMA_VERSION: (WMS_SCHEMA_SQL, 3),
}
