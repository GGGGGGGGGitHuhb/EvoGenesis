"""RNA World replication, mutation, competition and degradation rules."""

from __future__ import annotations

import random
from dataclasses import dataclass

from evogenesis.config import SimulationConfig
from evogenesis.state import RNAFamily, WorldState


@dataclass(frozen=True)
class TickDelta:
    """Summary of rule effects from one tick for event detection."""

    births: int = 0
    mutated_families: int = 0
    extinctions: int = 0
    resources_consumed: float = 0.0
    extinct_family_ids: tuple[str, ...] = ()
    extinct_lineage_ids: tuple[str, ...] = ()
    extinct_family_snapshots: tuple[dict[str, object], ...] = ()


class RNAWorldModule:
    """Apply RNA World rules while keeping IO and event concerns outside."""

    def __init__(self, config: SimulationConfig):
        self.config = config

    def advance(self, state: WorldState, rng: random.Random) -> TickDelta:
        """Advance RNA families by one tick of replication, mutation and decay."""

        state.resource_pool = min(
            self.config.max_resource_pool,
            state.resource_pool + self.config.resource_replenishment,
        )
        if not state.families:
            return TickDelta()

        births = 0
        mutated_families = 0
        resources_consumed = 0.0
        additions: list[RNAFamily] = []

        for family in list(state.families):
            family.age_ticks += 1
            if family.population <= 0:
                continue

            expected_births = self._expected_births(family, state)
            planned_births = self._stochastic_round(expected_births, rng)
            affordable_births = int(state.resource_pool // family.resource_cost)
            family_births = max(0, min(planned_births, affordable_births))
            if family_births == 0:
                continue

            cost = family_births * family.resource_cost
            state.resource_pool = max(0.0, state.resource_pool - cost)
            resources_consumed += cost
            births += family_births

            mutant_count = self._mutant_births(family_births, family, state, rng)
            normal_births = family_births - mutant_count
            family.population += normal_births

            for _ in range(mutant_count):
                if len(state.families) + len(additions) >= self.config.max_families:
                    family.population += 1
                    continue
                additions.append(self._mutate_family(family, state, rng))
                mutated_families += 1

        state.families.extend(additions)
        state.new_family_count += mutated_families
        extinct_families = self._apply_degradation(state, rng)
        self._record_lineage_windows(state)
        return TickDelta(
            births=births,
            mutated_families=mutated_families,
            extinctions=len(extinct_families),
            resources_consumed=round(resources_consumed, 4),
            extinct_family_ids=tuple(family["id"] for family in extinct_families),
            extinct_lineage_ids=tuple(
                sorted({str(family["lineage_id"]) for family in extinct_families})
            ),
            extinct_family_snapshots=tuple(extinct_families[:10]),
        )

    def _expected_births(self, family: RNAFamily, state: WorldState) -> float:
        resource_factor = min(1.0, state.resource_pool / max(1.0, family.resource_cost * family.population))
        length_penalty = max(0.35, 1.0 - max(0, family.length - 12) * 0.025)
        rate = (
            family.replication_rate
            * family.catalytic_power
            * state.energy_flux
            * resource_factor
            * length_penalty
        )
        return family.population * rate

    def _mutant_births(
        self,
        births: int,
        family: RNAFamily,
        state: WorldState,
        rng: random.Random,
    ) -> int:
        error_rate = (1.0 - family.replication_accuracy) * state.mutation_pressure
        expected_mutants = births * min(0.5, error_rate)
        return min(births, self._stochastic_round(expected_mutants, rng))

    def _mutate_family(
        self,
        parent: RNAFamily,
        state: WorldState,
        rng: random.Random,
    ) -> RNAFamily:
        sequence = mutate_sequence(parent.sequence, rng)
        family_id = f"rna-{state.next_family_index}"
        state.next_family_index += 1

        stability = _clamp(parent.stability + rng.uniform(-0.08, 0.08), 0.05, 0.98)
        replication_rate = _clamp(parent.replication_rate + rng.uniform(-0.012, 0.014), 0.001, 0.25)
        catalytic_power = _clamp(parent.catalytic_power + rng.uniform(-0.12, 0.16), 0.1, 3.0)
        accuracy = _clamp(parent.replication_accuracy + rng.uniform(-0.025, 0.02), 0.75, 0.995)
        cost = max(0.2, parent.resource_cost * (len(sequence) / max(1, parent.length)))

        return RNAFamily(
            id=family_id,
            sequence=sequence,
            population=1,
            replication_rate=round(replication_rate, 6),
            replication_accuracy=round(accuracy, 6),
            stability=round(stability, 6),
            catalytic_power=round(catalytic_power, 6),
            resource_cost=round(cost, 6),
            lineage_id=parent.lineage_id,
            parent_id=parent.id,
        )

    def _apply_degradation(self, state: WorldState, rng: random.Random) -> list[dict[str, object]]:
        extinct_families: list[dict[str, object]] = []
        survivors: list[RNAFamily] = []
        scarcity = 1.0 - min(1.0, state.resource_pool / max(1.0, self.config.max_resource_pool))
        for family in state.families:
            instability = 1.0 - family.stability
            environment = abs(state.temperature - 0.55) + scarcity * 0.8
            expected_loss = family.population * self.config.degradation_pressure * (instability + environment)
            loss = min(family.population, self._stochastic_round(expected_loss, rng))
            population_before = family.population
            family.population -= loss
            if family.population <= 0:
                extinct_families.append(
                    {
                        "id": family.id,
                        "lineage_id": family.lineage_id,
                        "population_before": population_before,
                        "population_after": 0,
                        "sequence": family.sequence,
                        "stability": family.stability,
                        "catalytic_power": family.catalytic_power,
                    }
                )
                continue
            survivors.append(family)
        state.families = survivors
        state.extinction_count += len(extinct_families)
        return extinct_families

    def _record_lineage_windows(self, state: WorldState) -> None:
        totals: dict[str, int] = {}
        for family in state.families:
            totals[family.lineage_id] = totals.get(family.lineage_id, 0) + family.population
        for lineage_id, population in totals.items():
            window = state.lineage_populations.setdefault(lineage_id, [])
            window.append(population)
            del window[:-25]

    def _stochastic_round(self, value: float, rng: random.Random) -> int:
        whole = int(value)
        return whole + (1 if rng.random() < value - whole else 0)


def mutate_sequence(sequence: str, rng: random.Random) -> str:
    """Return one RNA sequence variant through substitution, insertion or deletion."""

    bases = "AUGC"
    if not sequence:
        return rng.choice(bases)
    operation = rng.choices(["substitute", "insert", "delete"], weights=[0.7, 0.18, 0.12])[0]
    index = rng.randrange(len(sequence))
    if operation == "insert" and len(sequence) < 64:
        return sequence[:index] + rng.choice(bases) + sequence[index:]
    if operation == "delete" and len(sequence) > 3:
        return sequence[:index] + sequence[index + 1 :]
    replacement = rng.choice([base for base in bases if base != sequence[index]])
    return sequence[:index] + replacement + sequence[index + 1 :]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
