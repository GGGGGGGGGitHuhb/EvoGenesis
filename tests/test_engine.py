import unittest
from pathlib import Path

from evogenesis.config import SimulationConfig
from evogenesis.engine import SimulationEngine
from evogenesis.io.snapshots import load_snapshot
from evogenesis.state import compute_metrics
from tests.helpers import workspace_tempdir


def test_config(directory: str) -> SimulationConfig:
    return SimulationConfig(
        seed=42,
        snapshot_dir=str(Path(directory) / "saves"),
        log_dir=str(Path(directory) / "logs"),
        snapshot_interval=50,
        metrics_interval=10,
        initial_resource_pool=6000.0,
        resource_replenishment=20.0,
    )


def comparable_state(engine: SimulationEngine) -> dict[str, object]:
    data = engine.state.to_dict()
    for key in ["run_id", "world_created_at", "last_saved_at", "run_mode"]:
        data.pop(key, None)
    return data


class EngineTests(unittest.TestCase):
    def test_same_seed_is_reproducible(self):
        with workspace_tempdir() as left, workspace_tempdir() as right:
            engine_left = SimulationEngine(test_config(left))
            engine_right = SimulationEngine(test_config(right))

            engine_left.run(120)
            engine_right.run(120)

            self.assertEqual(comparable_state(engine_left), comparable_state(engine_right))

    def test_replication_consumes_resources_and_increases_population(self):
        with workspace_tempdir() as directory:
            engine = SimulationEngine(test_config(directory))
            starting_population = compute_metrics(engine.state).total_population
            starting_resources = engine.state.resource_pool

            engine.run(20)

            self.assertGreater(compute_metrics(engine.state).total_population, starting_population)
            self.assertLess(engine.state.resource_pool, starting_resources + 20 * 20.0)

    def test_mutation_creates_family_with_parent_lineage(self):
        with workspace_tempdir() as directory:
            config = test_config(directory)
            config = SimulationConfig(
                **{**config.to_dict(), "base_replication_accuracy": 0.75, "mutation_pressure": 2.0}
            )
            engine = SimulationEngine(config)

            engine.run(80)

            children = [family for family in engine.state.families if family.parent_id is not None]
            self.assertTrue(children)
            self.assertTrue(all(child.lineage_id == "lin-1" for child in children))

    def test_snapshot_resume_continues_tick_and_random_state(self):
        with workspace_tempdir() as directory:
            config = test_config(directory)
            continuous = SimulationEngine(config)
            continuous.run(80)

            split = SimulationEngine(config)
            split.run(50)
            snapshot = Path(config.snapshot_dir) / "latest.json"
            state, restored_config, random_state = load_snapshot(snapshot)
            resumed = SimulationEngine(restored_config, state=state, random_state=random_state)
            resumed.run(30)

            self.assertEqual(resumed.state.tick, 80)
            self.assertEqual(comparable_state(resumed), comparable_state(continuous))


if __name__ == "__main__":
    unittest.main()
