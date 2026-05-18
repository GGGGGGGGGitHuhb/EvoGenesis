"""JSON snapshot save and restore helpers."""

from __future__ import annotations

import base64
import json
import pickle
import random
from pathlib import Path
from typing import Any

from evogenesis.config import SimulationConfig
from evogenesis.state import WorldState

SNAPSHOT_VERSION = 1


class SnapshotError(ValueError):
    """Raised when a snapshot cannot be saved or restored safely."""


def save_snapshot(
    path: str | Path,
    state: WorldState,
    config: SimulationConfig,
    rng: random.Random,
) -> None:
    """Write a complete JSON snapshot including deterministic random state."""

    snapshot_path = Path(path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "snapshot_version": SNAPSHOT_VERSION,
        "config": config.to_dict(),
        "random_state": _encode_random_state(rng.getstate()),
        "state": state.to_dict(),
    }
    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def load_snapshot(path: str | Path) -> tuple[WorldState, SimulationConfig, object]:
    """Load state, configuration and random state from a snapshot file."""

    snapshot_path = Path(path)
    try:
        with snapshot_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise SnapshotError(f"Snapshot file not found: {snapshot_path}") from exc
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"Snapshot file is not valid JSON: {snapshot_path}") from exc

    required = {"snapshot_version", "config", "random_state", "state"}
    missing = sorted(required - set(payload))
    if missing:
        raise SnapshotError(f"Snapshot is missing required field(s): {', '.join(missing)}")
    if payload["snapshot_version"] != SNAPSHOT_VERSION:
        raise SnapshotError(
            f"Unsupported snapshot version: {payload['snapshot_version']} "
            f"(expected {SNAPSHOT_VERSION})"
        )

    try:
        config = SimulationConfig(**payload["config"])
        state = WorldState.from_dict(payload["state"])
        random_state = _decode_random_state(payload["random_state"])
    except (TypeError, KeyError, ValueError, pickle.PickleError) as exc:
        raise SnapshotError(f"Snapshot fields are invalid: {exc}") from exc
    return state, config, random_state


def _encode_random_state(random_state: object) -> str:
    data = pickle.dumps(random_state)
    return base64.b64encode(data).decode("ascii")


def _decode_random_state(encoded: Any) -> object:
    if not isinstance(encoded, str):
        raise SnapshotError("random_state must be encoded as a string.")
    return pickle.loads(base64.b64decode(encoded.encode("ascii")))
