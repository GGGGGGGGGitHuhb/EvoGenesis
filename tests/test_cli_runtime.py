import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from evogenesis.cli import main
from evogenesis.config import SimulationConfig
from evogenesis.engine import SimulationEngine
from evogenesis.io.snapshots import load_snapshot
from tests.helpers import workspace_tempdir


class CliRuntimeTests(unittest.TestCase):
    def test_steps_and_until_tick_semantics(self):
        with workspace_tempdir() as directory:
            config_path = Path(directory) / "config.json"
            config = SimulationConfig(
                seed=101,
                snapshot_dir=str(Path(directory) / "saves"),
                log_dir=str(Path(directory) / "logs"),
                snapshot_interval=50,
                metrics_interval=10,
                status_interval_ticks=10,
            )
            config_path.write_text(
                __import__("json").dumps(config.to_dict(), ensure_ascii=False),
                encoding="utf-8",
            )

            self.assertEqual(main(["run", "--config", str(config_path), "--steps", "25"]), 0)
            state, _config, _random_state = load_snapshot(Path(directory) / "saves" / "latest.json")
            self.assertEqual(state.tick, 25)

            self.assertEqual(
                main(
                    [
                        "run",
                        "--resume",
                        str(Path(directory) / "saves" / "latest.json"),
                        "--until-tick",
                        "40",
                    ]
                ),
                0,
            )
            state, _config, _random_state = load_snapshot(Path(directory) / "saves" / "latest.json")
            self.assertEqual(state.tick, 40)

    def test_until_tick_rejects_past_target(self):
        with workspace_tempdir() as directory:
            config = SimulationConfig(
                seed=202,
                snapshot_dir=str(Path(directory) / "saves"),
                log_dir=str(Path(directory) / "logs"),
            )
            engine = SimulationEngine(config)
            engine.run(10)

            code = main(
                [
                    "run",
                    "--resume",
                    str(Path(directory) / "saves" / "latest.json"),
                    "--until-tick",
                    "5",
                ]
            )

            self.assertEqual(code, 2)

    def test_pause_and_reset(self):
        with workspace_tempdir() as directory:
            config = SimulationConfig(
                seed=303,
                snapshot_dir=str(Path(directory) / "saves"),
                log_dir=str(Path(directory) / "logs"),
            )
            engine = SimulationEngine(config)
            engine.run(5)
            snapshot = Path(directory) / "saves" / "latest.json"

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["pause", "--snapshot", str(snapshot)])
            self.assertEqual(code, 0)
            self.assertIn("已暂停", output.getvalue())

            config_path = Path(directory) / "config.json"
            config_path.write_text(
                __import__("json").dumps(config.to_dict(), ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(main(["reset", "--config", str(config_path), "--yes"]), 0)
            self.assertFalse((Path(directory) / "saves").exists())
            self.assertTrue(Path("archives").exists())

    def test_chinese_output_contains_start_status_and_summary(self):
        with workspace_tempdir() as directory:
            config_path = Path(directory) / "config.json"
            config = SimulationConfig(
                seed=404,
                snapshot_dir=str(Path(directory) / "saves"),
                log_dir=str(Path(directory) / "logs"),
                status_interval_ticks=5,
            )
            config_path.write_text(
                __import__("json").dumps(config.to_dict(), ensure_ascii=False),
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                code = main(["run", "--config", str(config_path), "--steps", "5"])

            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("RNA 世界开始演化", text)
            self.assertIn("[状态]", text)
            self.assertIn("本次运行总结", text)


if __name__ == "__main__":
    unittest.main()
