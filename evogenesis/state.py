"""Serializable domain state for the RNA World simulation."""

from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class RNAFamily:
    """A related set of RNA sequences competing as one simulated family."""

    id: str
    sequence: str
    population: int
    replication_rate: float
    replication_accuracy: float
    stability: float
    catalytic_power: float
    resource_cost: float
    lineage_id: str
    parent_id: str | None
    age_ticks: int = 0

    @property
    def length(self) -> int:
        """Return the current sequence length."""

        return len(self.sequence)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this family for snapshots."""

        payload = asdict(self)
        payload["length"] = self.length
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RNAFamily":
        """Build a family from snapshot data."""

        payload = dict(data)
        payload.pop("length", None)
        return cls(**payload)


@dataclass
class EventRecord:
    """A state-derived event with evidence for why it was emitted."""

    id: str
    display_name: str
    tick: int
    category: str
    message: str
    evidence: dict[str, Any]
    affected_families: list[str] = field(default_factory=list)
    affected_lineages: list[str] = field(default_factory=list)
    effects: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this event for logs and snapshots."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventRecord":
        """Build an event record from snapshot data."""

        payload = dict(data)
        payload.setdefault("display_name", payload["id"])
        payload.setdefault("affected_families", [])
        payload.setdefault("affected_lineages", [])
        payload.setdefault("effects", {})
        return cls(**payload)


@dataclass
class Metrics:
    """A computed summary of the current RNA World state."""

    total_population: int
    family_count: int
    diversity: float
    average_length: float
    average_stability: float
    best_fitness: float
    resource_pool: float
    extinction_count: int
    new_family_count: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics for CSV and snapshot inspection."""

        return asdict(self)


@dataclass
class WorldState:
    """Complete mutable simulation state owned by the engine."""

    tick: int
    seed: int
    resource_pool: float
    temperature: float
    energy_flux: float
    mutation_pressure: float
    families: list[RNAFamily] = field(default_factory=list)
    event_counters: dict[str, int] = field(default_factory=dict)
    event_last_ticks: dict[str, int] = field(default_factory=dict)
    recent_events: list[EventRecord] = field(default_factory=list)
    extinction_count: int = 0
    new_family_count: int = 0
    next_family_index: int = 1
    lineage_populations: dict[str, list[int]] = field(default_factory=dict)
    run_id: str = field(default_factory=lambda: f"run-{uuid4().hex[:12]}")
    world_created_at: str = field(default_factory=lambda: _utc_now())
    last_saved_at: str | None = None
    years_per_tick: float = 1.0
    elapsed_simulation_years: float = 0.0
    run_mode: str = "steps"

    def to_dict(self) -> dict[str, Any]:
        """Serialize all domain fields for a snapshot."""

        return {
            "tick": self.tick,
            "seed": self.seed,
            "resource_pool": self.resource_pool,
            "temperature": self.temperature,
            "energy_flux": self.energy_flux,
            "mutation_pressure": self.mutation_pressure,
            "families": [family.to_dict() for family in self.families],
            "event_counters": dict(self.event_counters),
            "event_last_ticks": dict(self.event_last_ticks),
            "recent_events": [event.to_dict() for event in self.recent_events],
            "extinction_count": self.extinction_count,
            "new_family_count": self.new_family_count,
            "next_family_index": self.next_family_index,
            "lineage_populations": dict(self.lineage_populations),
            "run_id": self.run_id,
            "world_created_at": self.world_created_at,
            "last_saved_at": self.last_saved_at,
            "years_per_tick": self.years_per_tick,
            "elapsed_simulation_years": self.elapsed_simulation_years,
            "run_mode": self.run_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldState":
        """Build world state from snapshot data."""

        payload = dict(data)
        payload["families"] = [RNAFamily.from_dict(item) for item in data["families"]]
        payload["recent_events"] = [
            EventRecord.from_dict(item) for item in data.get("recent_events", [])
        ]
        payload.setdefault("run_id", f"run-{uuid4().hex[:12]}")
        payload.setdefault("world_created_at", _utc_now())
        payload.setdefault("last_saved_at", None)
        payload.setdefault("years_per_tick", 1.0)
        payload.setdefault("elapsed_simulation_years", payload["tick"] * payload["years_per_tick"])
        payload.setdefault("run_mode", "steps")
        return cls(**payload)


def compute_metrics(state: WorldState) -> Metrics:
    """Compute summary metrics directly from current families and resources."""

    live = [family for family in state.families if family.population > 0]
    total_population = sum(family.population for family in live)
    family_count = len(live)
    if total_population == 0:
        return Metrics(
            total_population=0,
            family_count=0,
            diversity=0.0,
            average_length=0.0,
            average_stability=0.0,
            best_fitness=0.0,
            resource_pool=round(state.resource_pool, 4),
            extinction_count=state.extinction_count,
            new_family_count=state.new_family_count,
        )

    diversity = 1.0 - sum((family.population / total_population) ** 2 for family in live)
    average_length = sum(family.length * family.population for family in live) / total_population
    average_stability = (
        sum(family.stability * family.population for family in live) / total_population
    )
    best_fitness = max(
        family.replication_rate * family.catalytic_power * family.replication_accuracy
        / family.resource_cost
        for family in live
    )
    return Metrics(
        total_population=total_population,
        family_count=family_count,
        diversity=round(diversity, 6),
        average_length=round(average_length, 4),
        average_stability=round(average_stability, 6),
        best_fitness=round(best_fitness, 6),
        resource_pool=round(state.resource_pool, 4),
        extinction_count=state.extinction_count,
        new_family_count=state.new_family_count,
    )


def initial_state(config: Any) -> WorldState:
    """Create the first RNA family from validated configuration parameters."""

    family = RNAFamily(
        id="rna-1",
        sequence=config.initial_sequence.upper(),
        population=config.initial_population,
        replication_rate=config.base_replication_rate,
        replication_accuracy=config.base_replication_accuracy,
        stability=config.base_stability,
        catalytic_power=config.base_catalytic_power,
        resource_cost=config.base_resource_cost,
        lineage_id="lin-1",
        parent_id=None,
    )
    return WorldState(
        tick=0,
        seed=config.seed,
        resource_pool=config.initial_resource_pool,
        temperature=config.temperature,
        energy_flux=config.energy_flux,
        mutation_pressure=config.mutation_pressure,
        families=[family] if config.initial_population > 0 else [],
        next_family_index=2,
        years_per_tick=config.years_per_tick,
    )


def family_snapshot(family: RNAFamily) -> dict[str, Any]:
    """Capture enough family detail to explain an event without dumping the world."""

    return {
        "id": family.id,
        "lineage_id": family.lineage_id,
        "population": family.population,
        "sequence": family.sequence,
        "stability": family.stability,
        "catalytic_power": family.catalytic_power,
    }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
