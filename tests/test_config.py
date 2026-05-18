import json
import unittest
from pathlib import Path

from evogenesis.config import ConfigError, load_config
from tests.helpers import workspace_tempdir


class ConfigTests(unittest.TestCase):
    def test_invalid_negative_resource_is_rejected(self):
        with workspace_tempdir() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"initial_resource_pool": -1}), encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_config(path)

    def test_default_config_loads_from_file(self):
        config = load_config("configs/rna_world.default.json")

        self.assertEqual(config.seed, 1337)
        self.assertGreater(config.initial_population, 0)


if __name__ == "__main__":
    unittest.main()
