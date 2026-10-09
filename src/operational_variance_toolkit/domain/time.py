"""Timezone conversion helpers for deterministic run records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def to_utc(value: datetime, facility_timezone: str) -> datetime:
    """Convert a naive local wall-clock datetime to a timezone-aware UTC datetime."""

    if value.tzinfo is not None:
        raise ValueError("value must be a naive local datetime")

    timezone = ZoneInfo(facility_timezone)
    _validate_local_wall_time(value, facility_timezone)
    aware_local = value.replace(tzinfo=timezone)
    round_trip = aware_local.astimezone(UTC).astimezone(timezone).replace(tzinfo=None)
    if round_trip != value:
        raise ValueError("local datetime is not a valid wall-clock time")
    return aware_local.astimezone(UTC)


def _validate_local_wall_time(value: datetime, facility_timezone: str) -> None:
    if facility_timezone != "America/New_York":
        return

    if value.year < 2000:
        return

    dst_start = _second_sunday_of_month(value.year, 3)
    dst_end = _first_sunday_of_month(value.year, 11)

    if dst_start <= value.date() < dst_end and value.hour == 2:
        raise ValueError("local datetime is not a valid wall-clock time")

    if value.date() == dst_end and value.hour == 1:
        raise ValueError("local datetime is not a valid wall-clock time")


def _second_sunday_of_month(year: int, month: int) -> datetime.date:
    first_day = datetime(year, month, 1).date()
    first_sunday = first_day + timedelta(days=(6 - first_day.weekday()) % 7)
    return first_sunday + timedelta(days=7)


def _first_sunday_of_month(year: int, month: int) -> datetime.date:
    first_day = datetime(year, month, 1).date()
    return first_day + timedelta(days=(6 - first_day.weekday()) % 7)


def to_facility_local(value: datetime, facility_timezone: str) -> datetime:
    """Convert an aware UTC datetime to the facility timezone."""

    if value.tzinfo is None:
        raise ValueError("value must be timezone-aware")

    timezone = ZoneInfo(facility_timezone)
    return value.astimezone(timezone)


def format_utc_timestamp(value: datetime) -> str:
    """Return a stable ISO 8601 UTC timestamp."""

    if value.tzinfo is None:
        raise ValueError("value must be timezone-aware")

    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
