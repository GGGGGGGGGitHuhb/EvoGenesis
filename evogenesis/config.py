"""Configuration loading and validation for EvoGenesis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a configuration file cannot be loaded or validated."""


@dataclass(frozen=True)
class SimulationConfig:
    """Validated parameters that control one RNA World simulation run."""

    seed: int = 1337
    initial_resource_pool: float = 8000.0
    resource_replenishment: float = 22.0
    max_resource_pool: float = 12000.0
    temperature: float = 0.62
    energy_flux: float = 1.0
    mutation_pressure: float = 1.0
    initial_population: int = 80
    initial_sequence: str = "AUGCUAGCUA"
    base_replication_rate: float = 0.055
    base_replication_accuracy: float = 0.965
    base_stability: float = 0.68
    base_catalytic_power: float = 1.0
    base_resource_cost: float = 1.0
    degradation_pressure: float = 0.018
    snapshot_interval: int = 1000
    metrics_interval: int = 50
    status_interval_ticks: int = 100
    time_unit_label: str = "年"
    years_per_tick: float = 1.0
    ticks_per_second: float = 20.0
    trace_all_ticks: bool = False
    snapshot_dir: str = "saves"
    log_dir: str = "logs"
    max_recent_events: int = 20
    max_families: int = 400

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable configuration summary."""

        return asdict(self)


def default_config() -> SimulationConfig:
    """Return the default RNA World configuration."""

    return SimulationConfig()


def load_config(path: str | Path | None = None) -> SimulationConfig:
    """Load a configuration JSON file or return defaults when no path is given."""

    if path is None:
        return default_config()

    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Configuration file is not valid JSON: {config_path}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Configuration root must be a JSON object.")

    allowed = set(SimulationConfig.__dataclass_fields__)
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ConfigError(f"Unknown configuration field(s): {', '.join(unknown)}")

    try:
        config = SimulationConfig(**raw)
    except TypeError as exc:
        raise ConfigError(str(exc)) from exc

    validate_config(config)
    return config


def validate_config(config: SimulationConfig) -> None:
    """Validate ranges whose biological meaning would break outside bounds."""

    checks = {
        "initial_resource_pool": config.initial_resource_pool >= 0,
        "resource_replenishment": config.resource_replenishment >= 0,
        "max_resource_pool": config.max_resource_pool > 0,
        "temperature": 0 <= config.temperature <= 1,
        "energy_flux": config.energy_flux >= 0,
        "mutation_pressure": config.mutation_pressure >= 0,
        "initial_population": config.initial_population >= 0,
        "base_replication_rate": config.base_replication_rate >= 0,
        "base_replication_accuracy": 0 <= config.base_replication_accuracy <= 1,
        "base_stability": 0 <= config.base_stability <= 1,
        "base_catalytic_power": config.base_catalytic_power >= 0,
        "base_resource_cost": config.base_resource_cost > 0,
        "degradation_pressure": config.degradation_pressure >= 0,
        "snapshot_interval": config.snapshot_interval > 0,
        "metrics_interval": config.metrics_interval > 0,
        "status_interval_ticks": config.status_interval_ticks > 0,
        "years_per_tick": config.years_per_tick > 0,
        "ticks_per_second": config.ticks_per_second > 0,
        "max_recent_events": config.max_recent_events > 0,
        "max_families": config.max_families > 0,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ConfigError(f"Invalid configuration value(s): {', '.join(failed)}")

    sequence = config.initial_sequence.upper()
    if not sequence or any(base not in "AUGC" for base in sequence):
        raise ConfigError("initial_sequence must contain only RNA bases A, U, G and C.")

    if config.initial_resource_pool > config.max_resource_pool:
        raise ConfigError("initial_resource_pool cannot exceed max_resource_pool.")

    if not config.time_unit_label:
        raise ConfigError("time_unit_label cannot be empty.")
