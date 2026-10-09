"""Pure deterministic physical-inventory state and actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from operational_variance_toolkit.errors import DataValidationError


@dataclass(frozen=True, slots=True)
class PhysicalPosition:
    location_id: str
    item_id: str | None
    qty_cases: int
    code_date: str | None


@dataclass(frozen=True, slots=True)
class PhysicalPickResult:
    requested_qty_cases: int
    picked_qty_cases: int
    short_qty_cases: int


class PhysicalAction(Protocol):
    action_id: str
    scheduled_utc: datetime
    priority: int

    def apply(self, state: PhysicalInventoryState) -> object: ...


@dataclass(frozen=True, slots=True)
class PhysicalPick:
    action_id: str
    scheduled_utc: datetime
    location_id: str
    item_id: str
    requested_qty_cases: int
    force_short: bool = False
    priority: int = 20

    def apply(self, state: PhysicalInventoryState) -> PhysicalPickResult:
        return state.pick(
            self.location_id,
            self.item_id,
            self.requested_qty_cases,
            force_short=self.force_short,
        )


@dataclass(frozen=True, slots=True)
class PhysicalTransfer:
    action_id: str
    scheduled_utc: datetime
    item_id: str
    source_location_id: str
    destination_location_id: str
    qty_cases: int
    priority: int = 10

    def apply(self, state: PhysicalInventoryState) -> None:
        state.transfer(
            self.item_id,
            self.source_location_id,
            self.destination_location_id,
            self.qty_cases,
        )


@dataclass(frozen=True, slots=True)
class PhysicalQuantityChange:
    action_id: str
    scheduled_utc: datetime
    location_id: str
    item_id: str
    qty_delta_cases: int
    priority: int = 30

    def apply(self, state: PhysicalInventoryState) -> None:
        state.change_quantity(self.location_id, self.item_id, self.qty_delta_cases)


class PhysicalInventoryState:
    """Track actual cases by location without recorded-system state."""

    def __init__(self, positions: tuple[PhysicalPosition, ...]) -> None:
        self._positions = {position.location_id: position for position in positions}
        if len(self._positions) != len(positions):
            raise DataValidationError("Physical state requires unique locations")
        self._require_valid()

    def position(self, location_id: str) -> PhysicalPosition:
        try:
            return self._positions[location_id]
        except KeyError as exc:
            raise DataValidationError(f"Unknown physical location: {location_id}") from exc

    def quantity(self, location_id: str, item_id: str) -> int:
        position = self.position(location_id)
        return position.qty_cases if position.item_id == item_id else 0

    def pick(
        self,
        location_id: str,
        item_id: str,
        requested_qty_cases: int,
        *,
        force_short: bool = False,
    ) -> PhysicalPickResult:
        if requested_qty_cases <= 0:
            raise DataValidationError("Physical pick quantity must be positive")
        position = self._require_item(location_id, item_id)
        available = position.qty_cases
        picked = min(requested_qty_cases, available)
        if force_short and picked == requested_qty_cases and requested_qty_cases > 1:
            picked -= 1
        self._replace(position, position.qty_cases - picked)
        return PhysicalPickResult(requested_qty_cases, picked, requested_qty_cases - picked)

    def transfer(
        self,
        item_id: str,
        source_location_id: str,
        destination_location_id: str,
        qty_cases: int,
    ) -> None:
        if qty_cases <= 0:
            raise DataValidationError("Physical transfer quantity must be positive")
        source = self._require_item(source_location_id, item_id)
        destination = self.position(destination_location_id)
        if destination.item_id not in {None, item_id}:
            raise DataValidationError("Physical transfer destination has a different item")
        if source.qty_cases < qty_cases:
            raise DataValidationError("Physical transfer exceeds source quantity")
        self._replace(source, source.qty_cases - qty_cases)
        self._positions[destination_location_id] = PhysicalPosition(
            location_id=destination.location_id,
            item_id=item_id,
            qty_cases=destination.qty_cases + qty_cases,
            code_date=destination.code_date or source.code_date,
        )
        self._require_valid()

    def change_quantity(self, location_id: str, item_id: str, qty_delta_cases: int) -> None:
        if qty_delta_cases == 0:
            raise DataValidationError("Physical quantity change must be nonzero")
        position = self._require_item(location_id, item_id)
        self._replace(position, position.qty_cases + qty_delta_cases)

    def quantities(self) -> dict[str, int]:
        return {
            location_id: position.qty_cases for location_id, position in self._positions.items()
        }

    def _require_item(self, location_id: str, item_id: str) -> PhysicalPosition:
        position = self.position(location_id)
        if position.item_id != item_id:
            raise DataValidationError("Physical item does not match location assignment")
        return position

    def _replace(self, position: PhysicalPosition, qty_cases: int) -> None:
        if qty_cases < 0:
            raise DataValidationError("Physical inventory cannot become negative")
        self._positions[position.location_id] = PhysicalPosition(
            position.location_id,
            position.item_id,
            qty_cases,
            position.code_date,
        )
        self._require_valid()

    def _require_valid(self) -> None:
        if any(position.qty_cases < 0 for position in self._positions.values()):
            raise DataValidationError("Physical inventory cannot be negative")


class ChronologicalActionRunner:
    """Apply physical actions in stable time, priority, and ID order."""

    def __init__(self) -> None:
        self._last_key: tuple[datetime, int, str] | None = None

    def run(
        self,
        state: PhysicalInventoryState,
        actions: tuple[PhysicalAction, ...],
    ) -> tuple[object, ...]:
        ordered = sorted(
            actions,
            key=lambda action: (action.scheduled_utc, action.priority, action.action_id),
        )
        return tuple(self.apply(state, action) for action in ordered)

    def apply(self, state: PhysicalInventoryState, action: PhysicalAction) -> object:
        key = (action.scheduled_utc, action.priority, action.action_id)
        if self._last_key is not None and key < self._last_key:
            raise DataValidationError(
                "Physical actions must execute chronologically: "
                f"{action.action_id} at {action.scheduled_utc.isoformat()} follows "
                f"{self._last_key[2]} at {self._last_key[0].isoformat()}"
            )
        self._last_key = key
        return action.apply(state)
