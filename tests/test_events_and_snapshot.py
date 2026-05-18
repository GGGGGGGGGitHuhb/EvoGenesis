import json
import unittest
from pathlib import Path

from evogenesis.config import SimulationConfig
from evogenesis.engine import SimulationEngine
from evogenesis.io.snapshots import SnapshotError, load_snapshot
from tests.helpers import workspace_tempdir


class EventsAndSnapshotTests(unittest.TestCase):
    def test_events_include_evidence_and_once_milestone_does_not_repeat(self):
        with workspace_tempdir() as directory:
            config = SimulationConfig(
                seed=7,
                snapshot_dir=str(Path(directory) / "saves"),
                log_dir=str(Path(directory) / "logs"),
                snapshot_interval=100,
                metrics_interval=10,
            )
            engine = SimulationEngine(config)

            engine.run(180)

            first_replicator_events = [
                event for event in engine.state.recent_events if event.id == "first_replicator"
            ]
            self.assertLessEqual(len(first_replicator_events), 1)
            self.assertTrue(all(event.evidence for event in engine.state.recent_events))
            self.assertTrue(all(event.display_name for event in engine.state.recent_events))

    def test_extinction_event_lists_family_ids(self):
        with workspace_tempdir() as directory:
            config = SimulationConfig(
                seed=11,
                initial_population=5,
                initial_resource_pool=0.0,
                resource_replenishment=0.0,
                base_stability=0.05,
                degradation_pressure=0.9,
                snapshot_dir=str(Path(directory) / "saves"),
                log_dir=str(Path(directory) / "logs"),
            )
            engine = SimulationEngine(config)

            engine.run(5)

            extinction_events = [
                event for event in engine.state.recent_events if event.id == "replicator_extinction"
            ]
            self.assertTrue(extinction_events)
            self.assertTrue(extinction_events[0].affected_families)
            self.assertIn("extinct_family_ids", extinction_events[0].evidence)

    def test_missing_snapshot_fields_are_rejected(self):
        with workspace_tempdir() as directory:
            path = Path(directory) / "broken.json"
            path.write_text(json.dumps({"snapshot_version": 1}), encoding="utf-8")

            with self.assertRaises(SnapshotError):
                load_snapshot(path)

    def test_resource_depletion_limits_growth(self):
        with workspace_tempdir() as directory:
            config = SimulationConfig(
                seed=9,
                initial_resource_pool=0.0,
                resource_replenishment=0.0,
                snapshot_dir=str(Path(directory) / "saves"),
                log_dir=str(Path(directory) / "logs"),
            )
            engine = SimulationEngine(config)
            starting_population = sum(family.population for family in engine.state.families)

            engine.run(30)

            ending_population = sum(family.population for family in engine.state.families)
            self.assertLessEqual(ending_population, starting_population)


if __name__ == "__main__":
    unittest.main()
