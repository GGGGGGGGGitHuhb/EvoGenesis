"""Simulation engine that owns ticks, random source and module scheduling."""

from __future__ import annotations

import random
from pathlib import Path

from evogenesis.config import SimulationConfig
from evogenesis.events import EventSystem
from evogenesis.io.history import HistoryWriter, format_event_for_console
from evogenesis.io.snapshots import save_snapshot
from evogenesis.modules.rna_world import RNAWorldModule
from evogenesis.summary import generate_run_summary
from evogenesis.state import WorldState, compute_metrics, initial_state


class SimulationEngine:
    """Coordinate RNA World rules, events, metrics and snapshots."""

    def __init__(
        self,
        config: SimulationConfig,
        state: WorldState | None = None,
        random_state: object | None = None,
    ):
        self.config = config
        self.state = state if state is not None else initial_state(config)
        self.rng = random.Random(self.state.seed)
        if random_state is not None:
            self.rng.setstate(random_state)
        self.rules = RNAWorldModule(config)
        self.events = EventSystem(config)
        self.history = HistoryWriter(config.log_dir)

    def run(self, steps: int, run_mode: str = "steps") -> list[str]:
        """Run a positive number of steps and return Chinese console lines."""

        if steps <= 0:
            raise ValueError("steps must be a positive integer.")

        start_tick = self.state.tick
        run_events = []
        console_lines: list[str] = []
        self.state.run_mode = run_mode
        for _ in range(steps):
            self.state.tick += 1
            self.state.elapsed_simulation_years = self.state.tick * self.config.years_per_tick
            delta = self.rules.advance(self.state, self.rng)
            events = self.events.evaluate(self.state, delta)
            run_events.extend(events)
            self.history.write_events(events)
            for event in events:
                console_lines.append(format_event_for_console(event))

            if self.state.tick % self.config.metrics_interval == 0:
                self.history.write_metrics(self.state.tick, compute_metrics(self.state))
            if self.state.tick % self.config.status_interval_ticks == 0:
                console_lines.append(self.status_line())
            if self.state.tick % self.config.snapshot_interval == 0:
                self.save_snapshot(Path(self.config.snapshot_dir) / f"tick-{self.state.tick}.json")

        self.history.write_metrics(self.state.tick, compute_metrics(self.state))
        self.save_snapshot(Path(self.config.snapshot_dir) / "latest.json")
        summary = generate_run_summary(start_tick, self.state, run_events, self.config)
        self.history.write_summary(summary.text)
        console_lines.append("本次运行总结：")
        console_lines.append(summary.text)
        return console_lines

    def save_snapshot(self, path: str | Path) -> None:
        """Persist a complete snapshot of the current engine state."""

        from evogenesis.state import _utc_now

        self.state.last_saved_at = _utc_now()
        save_snapshot(path, self.state, self.config, self.rng)

    def status_line(self) -> str:
        """Return one Chinese status line for periodic console observation."""

        metrics = compute_metrics(self.state)
        best = max(self.state.families, key=lambda family: family.population, default=None)
        best_text = "无"
        if best is not None:
            best_text = f"{best.id}/{best.lineage_id}/种群{best.population}"
        simulated_time = self.state.tick * self.config.years_per_tick
        return (
            f"[状态] tick={self.state.tick}，模拟时间={simulated_time:g}{self.config.time_unit_label}，"
            f"总种群={metrics.total_population}，家族数={metrics.family_count}，"
            f"多样性={metrics.diversity}，资源池={metrics.resource_pool}，"
            f"灭绝={metrics.extinction_count}，新家族={metrics.new_family_count}，优势家族={best_text}"
        )
