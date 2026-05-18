import tempfile
from pathlib import Path


def workspace_tempdir():
    root = Path("build") / "test-tmp"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)
