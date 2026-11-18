# Changelog

## 2026-11-18 — Batch 1 (Foundation)

- Created the project structure: data, docs, notebooks, `src/energy_futures` modules for each engine, tests, dashboard.
- Added `pyproject.toml` and `uv.lock` (Python 3.12; numpy, pandas, pyarrow, requests, pyyaml; pytest).
- Added `.gitignore` (secrets, data, environments, caches, model artefacts), `.env.example`, README.
- Added the tracking files: PROJECT_STATUS, DECISIONS, EXPERIMENT_LOG, CHANGELOG.
- Added `tests/test_foundation.py` (imports, folder structure, ignore rules).
