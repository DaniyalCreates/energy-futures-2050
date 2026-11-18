# Project status — Energy Futures 2050

_Last updated: 2026-11-18_

## 1. Current position
- **Batch 1 (Steps 1–8): COMPLETE.** Verified on macOS: 13 tests passed.
- **Batch 2 (Steps 9–16): COMPLETE.** Dataset v1 built and validated (see section 4). One Mac-side check remains open (section 7).
- **Next: Batch 3 (Steps 17–23), baselines.** Awaiting approval.

## 2. Completed tasks and evidence
| Step | Evidence |
| --- | --- |
| 9 Verify the NESO definitions | `docs/data_dictionary.md` (21 fields, MW, settlement-period rules) |
| 10 Target | D-010 confirmed: underlying demand = ND + embedded solar + embedded wind |
| 11–12 Acquisition | `ingest/neso.py`, `ingest/weather.py`; 17 NESO CSVs + 102 weather files; `data/raw/manifest.csv` (SHA-256) |
| 13 Inspection | Quality findings + sanity checks in `docs/data_dictionary.md` |
| 14 Cleaning | `clean/demand.py` (clock changes, duplicates, forecast rows, flags; stops on parse errors) |
| 15 Weather | `clean/weather.py`; aligned to period starts; equal-weight GB mean (D-012) |
| 16 Saved and versioned | `data/processed/demand_weather.parquet` + `dataset_version.json` |

## 3. Files (Batch 2)
configs/data.yaml; src/energy_futures/{config.py, pipeline.py, ingest/*, clean/*}; tests/test_clean_demand.py, tests/test_weather_align.py; docs/data_dictionary.md; docs/data_quality/quality_report.json; README, DECISIONS, CHANGELOG, EXPERIMENT_LOG.

## 4. Dataset provenance
v1: 298,032 half-hours, 2009-01-01 to 2025-12-31 UTC, no gaps. Config hash e0446e27f33da46a, manifest hash 31c6628cede87de2. NESO Open Data Licence; Open-Meteo CC BY 4.0 (non-commercial free tier). Data files are git-ignored; rebuild with `pipeline all`.

## 5. Experiments and results
No model experiments yet. Descriptive facts only: ND annual mean 35.9 → 26.2 GW and underlying demand 36.6 → 30.2 GW (2009 → 2025); daily temperature–demand correlation −0.78 (2019).

## 6. Tests
26 passed (Claude's sandbox on the Mac, 2026-11-18). Batch 1's 13 tests were verified natively on macOS.

## 7. Problems and open questions
- Claude's sandboxes can't reach NESO or Open-Meteo, so downloads run on Dani's Mac (D-013).
- macOS `.venv` import issue: `chflags -R nohidden .venv` applied; still to confirm that `uv run python -m energy_futures.pipeline build` works without `PYTHONPATH=src` (D-016).
- Weather uses reanalysis, which counts as perfect-weather information (D-009). The realistic-weather setting is needed before any comparison with NESO's forecast (Batch 4).
- Population weighting for weather is deferred (D-012).

## 8. Approved decisions
DECISIONS.md D-001 to D-016.

## 9. Next three tasks
1. Dani: confirm `uv run pytest` and `uv run python -m energy_futures.pipeline build` both work on macOS without PYTHONPATH.
2. Batch 3, Step 17: formulate the day-ahead task (forecast issued at a fixed cut-off; permitted inputs) and write it in DECISIONS.
3. Batch 3, Steps 18–19: chronological splits (train ≤2022, validate 2023, test 2024–2025) and the seasonal-naïve baseline.
