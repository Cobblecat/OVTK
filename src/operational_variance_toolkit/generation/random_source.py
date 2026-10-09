"""Deterministic named random streams for generation workflows."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Final

import numpy as np

from operational_variance_toolkit.errors import IdentityError

_STREAM_NAMES: Final[tuple[str, ...]] = (
    "master_items",
    "master_locations",
    "operators",
    "schedules",
    "opening_inventory",
    "operations_trips",
    "operations_picks",
    "operations_replenishment",
    "operations_quality",
    "operations_adjustments",
    "operations_system_events",
    "failure_replenishment_gap",
    "failure_qa_masking",
    "failure_selector_exposure",
)


def create_named_random_streams(
    seed: int, stream_names: Iterable[str] | None = None
) -> dict[str, np.random.Generator]:
    """Create independently seeded named random streams from one root seed."""

    if not isinstance(seed, int) or isinstance(seed, bool):
        raise IdentityError("seed must be an integer")

    resolved_names = tuple(stream_names or _STREAM_NAMES)
    if not resolved_names:
        return {}

    invalid_names = sorted(set(resolved_names) - set(_STREAM_NAMES))
    if invalid_names:
        joined = ", ".join(invalid_names)
        raise IdentityError(f"unsupported stream name(s): {joined}")

    return {name: np.random.default_rng(_derive_stream_seed(seed, name)) for name in resolved_names}


def _derive_stream_seed(seed: int, stream_name: str) -> np.random.SeedSequence:
    payload = f"{seed}:{stream_name}".encode()
    digest = hashlib.sha256(payload).digest()[:8]
    stream_value = int.from_bytes(digest, "big")
    return np.random.SeedSequence([seed, stream_value])
