"""Run metadata and deterministic run identity helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from operational_variance_toolkit.config import ProjectConfig
from operational_variance_toolkit.domain.time import to_facility_local
from operational_variance_toolkit.version import get_version


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    scenario_name: str
    scenario_version: str
    seed: int
    simulation_start_utc: datetime
    simulation_end_utc: datetime
    facility_timezone: str
    config_hash: str
    schema_version: str
    generator_version: str
    generated_at_utc: datetime
    source_code_revision: str | None = None


def build_run_record(
    config: ProjectConfig, *, generated_at_utc: datetime | None = None
) -> RunRecord:
    """Create a deterministic run record from configuration and metadata."""

    if config.run.start_utc >= config.run.end_utc:
        raise ValueError("run.start_utc must be before run.end_utc")

    if generated_at_utc is None:
        generated_at_utc = datetime.now(tz=UTC)
    if generated_at_utc.tzinfo is None:
        raise ValueError("generated_at_utc must be timezone-aware")

    run_id = build_run_id(
        scenario_version=config.run.scenario_version,
        config_hash=config.configuration_hash,
        seed=config.run.seed,
    )
    return RunRecord(
        run_id=run_id,
        scenario_name=config.run.scenario_name,
        scenario_version=config.run.scenario_version,
        seed=config.run.seed,
        simulation_start_utc=config.run.start_utc,
        simulation_end_utc=config.run.end_utc,
        facility_timezone=config.run.facility_timezone,
        config_hash=config.configuration_hash,
        schema_version="0.1.0",
        generator_version=get_version(),
        generated_at_utc=generated_at_utc,
        source_code_revision=None,
    )


def build_run_id(*, scenario_version: str, config_hash: str, seed: int) -> str:
    """Create a stable short run identifier from identity inputs."""

    payload = json.dumps(
        {
            "scenario_version": scenario_version,
            "config_hash": config_hash,
            "seed": seed,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"RUN-{digest[:16].upper()}"


def build_neutral_run_id(*, config_hash: str, seed: int, schema_version: str) -> str:
    """Create a stable WMS run identifier without scenario metadata."""

    payload = json.dumps(
        {
            "config_hash": config_hash,
            "schema_version": schema_version,
            "seed": seed,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"RUN-{digest[:16].upper()}"


def format_run_time(value: datetime, facility_timezone: str) -> str:
    """Return a facility-local human-readable timestamp."""

    local_value = to_facility_local(value, facility_timezone)
    return local_value.replace(tzinfo=None).isoformat(timespec="seconds")


def as_dict(record: RunRecord) -> dict[str, Any]:
    """Serialize a run record for downstream code or tests."""

    return {
        "run_id": record.run_id,
        "scenario_name": record.scenario_name,
        "scenario_version": record.scenario_version,
        "seed": record.seed,
        "simulation_start_utc": record.simulation_start_utc.isoformat(),
        "simulation_end_utc": record.simulation_end_utc.isoformat(),
        "facility_timezone": record.facility_timezone,
        "config_hash": record.config_hash,
        "schema_version": record.schema_version,
        "generator_version": record.generator_version,
        "generated_at_utc": record.generated_at_utc.isoformat(),
        "source_code_revision": record.source_code_revision,
    }
