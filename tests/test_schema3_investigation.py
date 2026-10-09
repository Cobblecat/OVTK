from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from operational_variance_toolkit.application.wms_generation import canonical_wms_content
from operational_variance_toolkit.application.wms_investigation import generate_wms_investigation
from operational_variance_toolkit.config import (
    FailuresConfig,
    SelectorFalseLeadConfig,
    load_project_config,
)
from operational_variance_toolkit.errors import DataValidationError, OutputExistsError
from operational_variance_toolkit.scenarios.investigation import InvestigationPolicy
from operational_variance_toolkit.simulation.read_model import BaselineInputs, SlotPlan
from operational_variance_toolkit.storage.database import connect_database, database_user_version
from operational_variance_toolkit.storage.ground_truth import canonical_ground_truth
from operational_variance_toolkit.validation.scenario import validate_scenario_artifacts

CONFIG = Path("configs/investigation.toml")


def test_investigation_policy_preserves_baseline_qa_when_masking_is_disabled() -> None:
    config = replace(
        load_project_config(CONFIG),
        failures=FailuresConfig(selector_false_lead=SelectorFalseLeadConfig(enabled=True)),
    )
    slot = SlotPlan(
        "ITEM-1",
        "PICK-1",
        "RESERVE-1",
        "ZONE-1",
        "FRZ",
        1,
        2,
        4,
        8,
        0.5,
        "A",
    )
    inputs = BaselineInputs(
        (),
        (slot,),
        (),
        ("SEL-1", "SEL-2"),
        (),
        (),
        "IC-1",
        ("ZONE-1",),
    )
    policy = InvestigationPolicy(config, inputs)

    assert policy.qa_policy(1, True, slot).adjustment_reason_code == "DAMAGE"
    assert policy.qa_policy(4, False, slot).adjustment_reason_code is None


@pytest.fixture()
def investigation(tmp_path: Path):
    return generate_wms_investigation(
        CONFIG, tmp_path / "investigation.sqlite3", tmp_path / "ground_truth.json"
    )


def test_schema3_investigation_generation_and_controlled_signatures(investigation) -> None:
    result = investigation
    assert result.validation.passed
    assert result.scenario_validation.passed
    assert result.physical_recorded_equal
    assert result.run_metadata.schema_version == "3.0.0"
    assert database_user_version(result.database_path) == 3
    assert result.operation_counts == result.operation_counts.__class__(
        trips=140,
        pick_events=1133,
        replenishment_tasks=78,
        qa_events=18,
        inventory_adjustments=22,
        system_events=4,
        closing_snapshots=192,
    )
    truth = json.loads(result.ground_truth_path.read_text(encoding="utf-8"))
    patterns = truth["patterns"]
    assert len(patterns["replenishment_gap"]["affected_pick_event_ids"]) == 28
    assert len(patterns["replenishment_gap"]["delayed_replenishment_task_ids"]) == 2
    assert len(patterns["replenishment_gap"]["recovery_adjustment_ids"]) == 8
    timing = patterns["replenishment_gap"]["timing_evidence"]
    assert len(timing) == 2
    assert all(row["wms_confirmed_utc"] < row["physical_completed_utc"] for row in timing)
    assert len(patterns["qa_masking"]["qa_event_ids"]) == 10
    assert len(patterns["qa_masking"]["adjustment_ids"]) == 10
    assert len(patterns["selector_false_lead"]["target_trip_ids"]) == 28
    assert len(patterns["selector_false_lead"]["exposed_peer_selector_ids"]) == 3
    assert validate_scenario_artifacts(result.database_path, result.ground_truth_path).passed


def test_schema3_investigation_closing_has_realistic_occupancy_and_supply(investigation) -> None:
    with connect_database(investigation.database_path) as connection:
        reserves = connection.execute(
            """SELECT COUNT(*), SUM(item_id IS NULL) FROM inventory_master AS i
               JOIN location_master AS l USING (run_id, location_id)
               WHERE i.run_id = ? AND l.location_type = 'RESERVE'""",
            (investigation.run_metadata.run_id,),
        ).fetchone()
        picks = connection.execute(
            """SELECT i.qty_on_hand_cases, i.maximum_qty_cases FROM inventory_master AS i
               JOIN location_master AS l USING (run_id, location_id)
               WHERE i.run_id = ? AND l.location_type = 'PICK' AND i.item_id IS NOT NULL""",
            (investigation.run_metadata.run_id,),
        ).fetchall()
        reserve_supply = connection.execute(
            """SELECT COUNT(*) FROM inventory_master AS i JOIN location_master AS l
                 USING (run_id, location_id)
               WHERE i.run_id = ? AND l.location_type = 'RESERVE'
                 AND i.item_id IS NOT NULL AND i.qty_on_hand_cases > 0""",
            (investigation.run_metadata.run_id,),
        ).fetchone()[0]
        completed = connection.execute(
            "SELECT COUNT(*) FROM replenishment_task WHERE run_id = ? AND status = 'CONFIRMED'",
            (investigation.run_metadata.run_id,),
        ).fetchone()[0]
    assert 0.10 <= reserves[1] / reserves[0] <= 0.20
    assert 0 < sum(row[0] == 0 for row in picks) <= len(picks) // 10
    assert 0 < sum(row[1] and row[0] * 100 >= row[1] * 90 for row in picks) <= len(picks) // 10
    assert reserve_supply >= reserves[0] * 0.75
    assert completed > 0


def test_schema3_investigation_same_seed_is_canonical_and_changed_seed_valid(
    tmp_path: Path,
) -> None:
    first = generate_wms_investigation(CONFIG, tmp_path / "one.sqlite3", tmp_path / "one.json")
    second = generate_wms_investigation(CONFIG, tmp_path / "two.sqlite3", tmp_path / "two.json")
    assert canonical_wms_content(first.database_path) == canonical_wms_content(second.database_path)
    assert canonical_ground_truth(first.ground_truth_path) == canonical_ground_truth(
        second.ground_truth_path
    )

    changed_config = tmp_path / "changed.toml"
    changed_config.write_text(
        CONFIG.read_text(encoding="utf-8").replace("seed = 20260801", "seed = 20260802"),
        encoding="utf-8",
    )
    changed = generate_wms_investigation(
        changed_config, tmp_path / "changed.sqlite3", tmp_path / "changed.json"
    )
    assert canonical_wms_content(first.database_path) != canonical_wms_content(
        changed.database_path
    )
    assert canonical_ground_truth(first.ground_truth_path) != canonical_ground_truth(
        changed.ground_truth_path
    )
    assert changed.validation.passed and changed.scenario_validation.passed


def test_schema3_investigation_refuses_existing_outputs(tmp_path: Path) -> None:
    database = tmp_path / "investigation.sqlite3"
    truth = tmp_path / "truth.json"
    truth.write_text("existing", encoding="utf-8")
    with pytest.raises(OutputExistsError):
        generate_wms_investigation(CONFIG, database, truth)
    assert not database.exists()
    assert truth.read_text(encoding="utf-8") == "existing"


def test_schema3_investigation_cleans_database_after_driver_failure(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "incomplete.sqlite3"
    truth = tmp_path / "truth.json"

    def fail_driver(*args, **kwargs):
        raise DataValidationError("injected driver failure")

    monkeypatch.setattr(
        "operational_variance_toolkit.application.wms_investigation.run_baseline_protocol",
        fail_driver,
    )
    with pytest.raises(DataValidationError, match="injected driver failure"):
        generate_wms_investigation(CONFIG, database, truth)
    assert not database.exists()
    assert not truth.exists()


def test_schema3_investigation_cli_generate_and_scenario_check(tmp_path: Path, run_tool) -> None:
    database = tmp_path / "cli.sqlite3"
    truth = tmp_path / "cli.json"
    generated = run_tool(
        "generate", "--config", str(CONFIG), "--output", str(database), "--ground-truth", str(truth)
    )
    assert generated.returncode == 0
    assert "Schema-3 investigation WMS generated" in generated.stdout
    checked = run_tool("scenario-check", "--database", str(database), "--ground-truth", str(truth))
    assert checked.returncode == 0
    assert "Scenario validation status: PASS" in checked.stdout
