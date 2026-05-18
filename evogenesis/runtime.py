"""Runtime control helpers such as locks and reset archives."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class RuntimeLockError(RuntimeError):
    """Raised when another simulation is already writing the same output."""


@dataclass
class RuntimeLock:
    """A small lock file that prevents concurrent writes to latest snapshots."""

    lock_path: Path

    @classmethod
    def acquire(cls, snapshot_dir: str | Path) -> "RuntimeLock":
        """Create an exclusive lock file in the snapshot directory."""

        directory = Path(snapshot_dir)
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = directory / ".evogenesis.lock"
        try:
            with lock_path.open("x", encoding="utf-8") as handle:
                handle.write(f"started_at={datetime.now().isoformat(timespec='seconds')}\n")
        except FileExistsError as exc:
            raise RuntimeLockError(
                f"检测到运行锁 {lock_path}，同一输出目录可能已有模拟在运行。"
            ) from exc
        return cls(lock_path)

    def release(self) -> None:
        """Remove the lock file if it is still present."""

        self.lock_path.unlink(missing_ok=True)

    def __enter__(self) -> "RuntimeLock":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()


def archive_runtime_outputs(
    snapshot_dir: str | Path,
    log_dir: str | Path,
    archive_root: str | Path = "archives",
) -> Path:
    """Move saves and logs into a timestamped archive instead of deleting them."""

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = Path(archive_root)
    archive_dir = root / f"reset-{timestamp}"
    suffix = 1
    while archive_dir.exists():
        suffix += 1
        archive_dir = root / f"reset-{timestamp}-{suffix}"
    archive_dir.mkdir(parents=True, exist_ok=False)
    for source in [Path(snapshot_dir), Path(log_dir)]:
        if source.exists():
            target = archive_dir / source.name
            shutil.move(str(source), str(target))
    return archive_dir
