from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.domain.identifiers import (
    generate_code_identifier,
    generate_identifier,
    generate_identifier_sequence,
)
from operational_variance_toolkit.domain.run import build_run_record
from operational_variance_toolkit.domain.time import format_utc_timestamp, to_facility_local, to_utc
from operational_variance_toolkit.errors import IdentityError
from operational_variance_toolkit.generation.random_source import create_named_random_streams


def test_identical_inputs_produce_same_run_id(baseline_config_path: Path) -> None:
    config = load_project_config(baseline_config_path)

    first = build_run_record(config, generated_at_utc=datetime(2026, 5, 4, 12, 0, tzinfo=UTC))
    second = build_run_record(config, generated_at_utc=datetime(2026, 5, 4, 12, 0, tzinfo=UTC))

    assert first.run_id == second.run_id


def test_changed_identity_inputs_change_run_id(baseline_config_path: Path) -> None:
    config = load_project_config(baseline_config_path)

    first = build_run_record(config, generated_at_utc=datetime(2026, 5, 4, 12, 0, tzinfo=UTC))
    changed_config = load_project_config(baseline_config_path)
    changed_config = type(changed_config)(
        run=type(changed_config.run)(
            scenario_name=changed_config.run.scenario_name,
            scenario_version="0.2.0",
            seed=changed_config.run.seed,
            start_utc=changed_config.run.start_utc,
            end_utc=changed_config.run.end_utc,
            facility_timezone=changed_config.run.facility_timezone,
        ),
        facility=changed_config.facility,
        dimensions=changed_config.dimensions,
        storage=changed_config.storage,
    )

    second = build_run_record(
        changed_config, generated_at_utc=datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    )

    assert first.run_id != second.run_id


def test_generation_timestamp_does_not_change_run_id(baseline_config_path: Path) -> None:
    config = load_project_config(baseline_config_path)

    first = build_run_record(config, generated_at_utc=datetime(2026, 5, 4, 12, 0, tzinfo=UTC))
    second = build_run_record(config, generated_at_utc=datetime(2026, 5, 4, 13, 0, tzinfo=UTC))

    assert first.run_id == second.run_id


def test_identifier_examples_are_stable_and_human_readable() -> None:
    assert generate_identifier("FAC", 1, width=3) == "FAC-001"
    assert generate_identifier("LOC-FRZ", 1, width=3) == "LOC-FRZ-001"
    assert generate_identifier("ITEM", 1, width=4) == "ITEM-0001"
    assert generate_identifier("OP-SEL", 1, width=3) == "OP-SEL-001"
    assert generate_code_identifier("ZONE", "FRZ") == "ZONE-FRZ"


def test_identifier_sequence_is_stable_and_human_readable() -> None:
    sequence = generate_identifier_sequence("ITEM", 3, start=1, width=4)

    assert sequence == ["ITEM-0001", "ITEM-0002", "ITEM-0003"]


def test_named_random_streams_are_repeatable_and_isolated() -> None:
    first = create_named_random_streams(12345, ["operators", "schedules", "opening_inventory"])
    second = create_named_random_streams(12345, ["operators", "schedules", "opening_inventory"])

    first_alpha = first["operators"].integers(0, 100, size=5)
    first_beta = first["schedules"].integers(0, 100, size=5)
    second_alpha = second["operators"].integers(0, 100, size=5)
    second_beta = second["schedules"].integers(0, 100, size=5)

    assert first_alpha.tolist() == second_alpha.tolist()
    assert first_beta.tolist() == second_beta.tolist()

    first["operators"].integers(0, 100, size=5)
    assert (
        first["schedules"].integers(0, 100, size=5).tolist()
        == second["schedules"].integers(0, 100, size=5).tolist()
    )


def test_named_random_streams_are_independent_of_name_order() -> None:
    first = create_named_random_streams(12345, ["opening_inventory", "operators", "schedules"])
    second = create_named_random_streams(12345, ["schedules", "operators", "opening_inventory"])

    assert (
        first["operators"].integers(0, 100, size=3).tolist()
        == second["operators"].integers(0, 100, size=3).tolist()
    )
    assert (
        first["schedules"].integers(0, 100, size=3).tolist()
        == second["schedules"].integers(0, 100, size=3).tolist()
    )


def test_named_random_streams_reject_unsupported_names() -> None:
    with pytest.raises(IdentityError):
        create_named_random_streams(12345, ["operators", "unsupported"])


def test_time_helpers_convert_utc_and_local_time_for_new_york() -> None:
    utc_value = to_utc(datetime(2026, 5, 4, 3, 30), "America/New_York")
    assert utc_value == datetime(2026, 5, 4, 7, 30, tzinfo=UTC)

    local_value = to_facility_local(datetime(2026, 5, 4, 7, 30, tzinfo=UTC), "America/New_York")
    assert local_value == datetime(2026, 5, 4, 3, 30, tzinfo=ZoneInfo("America/New_York"))


def test_time_helpers_handle_dst_boundary_in_new_york() -> None:
    before_spring_forward = to_utc(datetime(2026, 3, 8, 1, 30), "America/New_York")
    after_spring_forward = to_utc(datetime(2026, 3, 8, 3, 30), "America/New_York")

    assert before_spring_forward == datetime(2026, 3, 8, 6, 30, tzinfo=UTC)
    assert after_spring_forward == datetime(2026, 3, 8, 7, 30, tzinfo=UTC)

    round_trip = to_facility_local(datetime(2026, 3, 8, 7, 30, tzinfo=UTC), "America/New_York")
    assert round_trip == datetime(2026, 3, 8, 3, 30, tzinfo=ZoneInfo("America/New_York"))


def test_time_helpers_reject_nonexistent_and_ambiguous_local_times() -> None:
    with pytest.raises(ValueError):
        to_utc(datetime(2026, 3, 9, 2, 30), "America/New_York")

    with pytest.raises(ValueError):
        to_utc(datetime(2026, 11, 1, 1, 30), "America/New_York")


def test_utc_timestamp_formatting_is_stable() -> None:
    assert format_utc_timestamp(datetime(2026, 5, 4, 7, 30, tzinfo=UTC)) == "2026-05-04T07:30:00Z"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 5, 4, 7, 0, tzinfo=UTC), datetime(2026, 5, 4, 7, 0, tzinfo=UTC)),
        (datetime(2026, 5, 5, 7, 0, tzinfo=UTC), datetime(2026, 5, 4, 7, 0, tzinfo=UTC)),
    ],
)
def test_invalid_run_boundaries_are_rejected(
    start: datetime, end: datetime, baseline_config_path: Path
) -> None:
    config = load_project_config(baseline_config_path)
    config = type(config)(
        run=type(config.run)(
            scenario_name=config.run.scenario_name,
            scenario_version=config.run.scenario_version,
            seed=config.run.seed,
            start_utc=start,
            end_utc=end,
            facility_timezone=config.run.facility_timezone,
        ),
        facility=config.facility,
        dimensions=config.dimensions,
        storage=config.storage,
    )

    with pytest.raises(ValueError, match="before"):
        build_run_record(config, generated_at_utc=datetime(2026, 5, 4, 12, 0, tzinfo=UTC))


@pytest.mark.parametrize(
    ("prefix", "value", "width"),
    [("", 1, 4), ("BAD prefix", 1, 4), ("ITEM", -1, 4)],
)
def test_invalid_identifier_inputs_are_rejected(prefix: str, value: int, width: int) -> None:
    with pytest.raises(IdentityError):
        generate_identifier(prefix, value, width=width)


def test_invalid_code_identifier_inputs_are_rejected() -> None:
    with pytest.raises(IdentityError):
        generate_code_identifier("ZONE", "")
