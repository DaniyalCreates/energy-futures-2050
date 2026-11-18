# Changelog

## 2026-11-18 — Batch 1 (Foundation)

- Created the project structure: data, docs, notebooks, `src/energy_futures` modules for each engine, tests, dashboard.
- Added `pyproject.toml` and `uv.lock` (Python 3.12; numpy, pandas, pyarrow, requests, pyyaml; pytest).
- Added `.gitignore` (secrets, data, environments, caches, model artefacts), `.env.example`, README.
- Added the tracking files: PROJECT_STATUS, DECISIONS, EXPERIMENT_LOG, CHANGELOG.
- Added `tests/test_foundation.py` (imports, folder structure, ignore rules).

## 2026-11-18 — Batch 2 (Data acquisition and validation)

- Added NESO and Open-Meteo download scripts with a SHA-256 raw-data manifest; `configs/data.yaml`.
- Added clock-change-aware demand cleaning, duplicate and forecast-row handling, plausibility flags, and the underlying-demand target.
- Added weather alignment to half-hour period starts and equal-weight GB means.
- Added `energy_futures.pipeline` (download / build / all) and dataset versioning.
- Fixed the 2023 date-format parse (a whole year had been lost in the first build); the build now stops on parse errors.
- Added the `flag_tsd_invalid` flag; `docs/data_dictionary.md` now covers version v1, quality findings and sanity checks.
- Tests: 26 passing.
