"""Batch 1 foundation checks: environment imports and git-ignore safety."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_core_dependencies_import():
    import numpy, pandas, pyarrow, requests, yaml  # noqa: F401
    import energy_futures  # noqa: F401


def test_expected_structure_exists():
    for rel in ["data/raw", "data/interim", "data/processed", "src/energy_futures/forecast",
                "src/energy_futures/scenarios", "src/energy_futures/uncertainty",
                "src/energy_futures/optimise", "tests", "docs", "dashboard"]:
        assert (ROOT / rel).is_dir(), rel


@pytest.mark.skipif(not (ROOT / ".git").exists() or shutil.which("git") is None,
                    reason="not a git repository")
@pytest.mark.parametrize("path", [
    ".env", ".env.local", "data/raw/demand.csv", "data/processed/x.parquet",
    ".venv/bin/python", "models/model.pkl", "outputs/fig.png", "credentials.json",
])
def test_sensitive_and_generated_paths_are_ignored(path):
    r = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT)
    assert r.returncode == 0, f"{path} is NOT ignored"


@pytest.mark.skipif(not (ROOT / ".git").exists(), reason="not a git repository")
@pytest.mark.parametrize("path", [".env.example", "data/raw/.gitkeep", "README.md"])
def test_intended_files_are_not_ignored(path):
    r = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT)
    assert r.returncode == 1, f"{path} is wrongly ignored"
