"""State-derived event detection for RNA World."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from evogenesis.config import SimulationConfig
from evogenesis.modules.rna_world import TickDelta
from evogenesis.state import EventRecord, WorldState, compute_metrics, family_snapshot


EventCheck = Callable[[WorldState, TickDelta], EventRecord | None]


@dataclass(frozen=True)
class EventDefinition:
    """Declarative event metadata with a condition function."""

    id: str
    name: str
    display_name: str
    category: str
    era: str
    cooldown: int | None
    once: bool
    severity: str
    check: EventCheck


class EventSystem:
    """Evaluate RNA World events without directly changing simulation rules."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.definitions = self._build_definitions()

    def evaluate(self, state: WorldState, delta: TickDelta) -> list[EventRecord]:
        """Return records whose conditions are satisfied at the current tick."""

        emitted: list[EventRecord] = []
        for definition in self.definitions:
            if definition.once and state.event_counters.get(definition.id, 0) > 0:
                continue
            last_tick = state.event_last_ticks.get(definition.id)
            if (
                definition.cooldown is not None
                and last_tick is not None
                and state.tick - last_tick < definition.cooldown
            ):
                continue
            record = definition.check(state, delta)
            if record is None:
                continue
            emitted.append(record)
            state.event_counters[definition.id] = state.event_counters.get(definition.id, 0) + 1
            state.event_last_ticks[definition.id] = state.tick
            state.recent_events.append(record)
            del state.recent_events[: -self.config.max_recent_events]
        return emitted

    def _build_definitions(self) -> list[EventDefinition]:
        return [
            EventDefinition("first_replicator", "First Replicator", "首个复制子扩张", "里程碑", "RNA World", None, True, "low", self._first_replicator),
            EventDefinition("stable_replicator_lineage", "Stable Replicator Lineage", "稳定复制子谱系", "里程碑", "RNA World", None, True, "medium", self._stable_lineage),
            EventDefinition("mutation_burst", "Mutation Burst", "突变爆发", "趋势", "RNA World", 120, False, "medium", self._mutation_burst),
            EventDefinition("dominant_lineage", "Dominant Lineage", "优势谱系形成", "趋势", "RNA World", 300, False, "medium", self._dominant_lineage),
            EventDefinition("resource_crash", "Resource Crash", "资源崩溃", "趋势", "RNA World", 200, False, "high", self._resource_crash),
            EventDefinition("replicator_extinction", "Replicator Extinction", "复制子灭绝", "趋势", "RNA World", 100, False, "medium", self._replicator_extinction),
            EventDefinition("catalytic_breakthrough", "Catalytic Breakthrough", "催化突破", "里程碑", "RNA World", None, True, "medium", self._catalytic_breakthrough),
            EventDefinition("complexity_increase", "Complexity Increase", "复杂度上升", "里程碑", "RNA World", None, True, "medium", self._complexity_increase),
        ]

    def _first_replicator(self, state: WorldState, delta: TickDelta) -> EventRecord | None:
        metrics = compute_metrics(state)
        if state.tick >= 1 and delta.births > 0 and metrics.total_population > self.config.initial_population:
            return self._record(
                "first_replicator",
                state,
                "复制子在消耗资源后成功扩张，RNA 世界出现可持续复制的起点。",
                {
                    "births": delta.births,
                    "total_population": metrics.total_population,
                    "resources_consumed": delta.resources_consumed,
                },
                affected_families=[family.id for family in state.families[:3]],
                affected_lineages=sorted({family.lineage_id for family in state.families}),
            )
        return None

    def _stable_lineage(self, state: WorldState, delta: TickDelta) -> EventRecord | None:
        del delta
        metrics = compute_metrics(state)
        if metrics.total_population < 250:
            return None
        for lineage_id, window in state.lineage_populations.items():
            if len(window) < 20 or min(window) <= 0:
                continue
            lineage_population = sum(
                family.population for family in state.families if family.lineage_id == lineage_id
            )
            share = lineage_population / metrics.total_population
            lineage_families = [family for family in state.families if family.lineage_id == lineage_id]
            accuracy = sum(f.replication_accuracy * f.population for f in lineage_families) / max(1, lineage_population)
            if share >= 0.45 and accuracy >= 0.93:
                return self._record(
                    "stable_replicator_lineage",
                    state,
                    "一个谱系在观察窗口内持续存在，并保持较高复制准确率。",
                    {
                        "lineage_id": lineage_id,
                        "family_ids": [family.id for family in lineage_families[:10]],
                        "family_snapshots": [family_snapshot(family) for family in lineage_families[:5]],
                        "population": lineage_population,
                        "population_share": round(share, 4),
                        "replication_accuracy": round(accuracy, 6),
                        "window_ticks": len(window),
                    },
                    affected_families=[family.id for family in lineage_families[:10]],
                    affected_lineages=[lineage_id],
                )
        return None

    def _mutation_burst(self, state: WorldState, delta: TickDelta) -> EventRecord | None:
        if delta.mutated_families >= 3:
            return self._record(
                "mutation_burst",
                state,
                "活跃复制中同一 tick 出现多个 RNA 变体，突变探索明显增强。",
                {
                    "new_families_this_tick": delta.mutated_families,
                    "births": delta.births,
                    "mutation_pressure": state.mutation_pressure,
                },
            )
        return None

    def _dominant_lineage(self, state: WorldState, delta: TickDelta) -> EventRecord | None:
        del delta
        metrics = compute_metrics(state)
        if metrics.total_population < 300:
            return None
        totals: dict[str, int] = {}
        for family in state.families:
            totals[family.lineage_id] = totals.get(family.lineage_id, 0) + family.population
        if not totals:
            return None
        lineage_id, population = max(totals.items(), key=lambda item: item[1])
        share = population / metrics.total_population
        if share >= 0.72 and metrics.family_count >= 3:
            lineage_families = [
                family for family in state.families if family.lineage_id == lineage_id
            ]
            return self._record(
                "dominant_lineage",
                state,
                "一个谱系在多家族资源竞争中占据主导。",
                {
                    "lineage_id": lineage_id,
                    "family_ids": [family.id for family in lineage_families[:10]],
                    "family_snapshots": [family_snapshot(family) for family in lineage_families[:5]],
                    "population": population,
                    "population_share": round(share, 4),
                    "family_count": metrics.family_count,
                },
                affected_families=[family.id for family in lineage_families[:10]],
                affected_lineages=[lineage_id],
            )
        return None

    def _resource_crash(self, state: WorldState, delta: TickDelta) -> EventRecord | None:
        del delta
        threshold = self.config.max_resource_pool * 0.08
        if state.resource_pool <= threshold:
            return self._record(
                "resource_crash",
                state,
                "资源池低于崩溃阈值，复制增长受到明显限制。",
                {
                    "resource_pool": round(state.resource_pool, 4),
                    "threshold": round(threshold, 4),
                },
            )
        return None

    def _replicator_extinction(self, state: WorldState, delta: TickDelta) -> EventRecord | None:
        if delta.extinctions > 0:
            return self._record(
                "replicator_extinction",
                state,
                "一个或多个 RNA 家族在本 tick 降解至灭绝。",
                {
                    "extinctions_this_tick": delta.extinctions,
                    "extinct_family_ids": list(delta.extinct_family_ids[:10]),
                    "extinct_family_count": len(delta.extinct_family_ids),
                    "truncated": len(delta.extinct_family_ids) > 10,
                    "family_snapshots": list(delta.extinct_family_snapshots),
                    "total_extinctions": state.extinction_count,
                },
                affected_families=list(delta.extinct_family_ids[:10]),
                affected_lineages=list(delta.extinct_lineage_ids),
            )
        return None

    def _catalytic_breakthrough(self, state: WorldState, delta: TickDelta) -> EventRecord | None:
        del delta
        best = max(state.families, key=lambda family: family.catalytic_power, default=None)
        if best is not None and best.catalytic_power >= self.config.base_catalytic_power * 1.45:
            return self._record(
                "catalytic_breakthrough",
                state,
                "一个突变 RNA 家族获得了显著更强的催化复制能力。",
                {
                    "family_id": best.id,
                    "lineage_id": best.lineage_id,
                    "family_snapshots": [family_snapshot(best)],
                    "catalytic_power": best.catalytic_power,
                    "baseline": self.config.base_catalytic_power,
                },
                affected_families=[best.id],
                affected_lineages=[best.lineage_id],
            )
        return None

    def _complexity_increase(self, state: WorldState, delta: TickDelta) -> EventRecord | None:
        del delta
        metrics = compute_metrics(state)
        if metrics.average_length >= len(self.config.initial_sequence) + 4 and metrics.family_count >= 5:
            return self._record(
                "complexity_increase",
                state,
                "平均 RNA 长度上升，同时仍有多个家族保持存活。",
                {
                    "average_length": metrics.average_length,
                    "initial_length": len(self.config.initial_sequence),
                    "family_count": metrics.family_count,
                },
            )
        return None

    def _record(
        self,
        event_id: str,
        state: WorldState,
        message: str,
        evidence: dict[str, object],
        affected_families: list[str] | None = None,
        affected_lineages: list[str] | None = None,
    ) -> EventRecord:
        definition = next(definition for definition in self.definitions if definition.id == event_id)
        return EventRecord(
            id=event_id,
            display_name=definition.display_name,
            tick=state.tick,
            category=definition.category,
            message=message,
            evidence=evidence,
            affected_families=affected_families or [],
            affected_lineages=affected_lineages or [],
            effects={"event_counter_incremented": event_id},
        )
