# Project status — Energy Futures 2050

_Last updated: 2026-11-18_

## 1. Current position
- **Batch 1 (Steps 1–8): COMPLETE.** Verified on macOS: 13 tests passed.
- **Batch 2 (Steps 9–16): COMPLETE.** Dataset v1 built and validated (see section 4). One Mac-side check remains open (section 7).
- **Batch 3 (Steps 17–23): COMPLETE.** EXP-001 baselines on validation 2023 (see section 5).
- **Batch 4 (Steps 24–30): COMPLETE.** EXP-002/003/004; report `docs/results/forecasting_report.md`.
- **Batch 5 (Steps 31–36): COMPLETE.** EXP-005; report `docs/results/scenarios_report.md`; assumptions `docs/assumptions.md`.
- **Next: Batch 6 (Steps 37–42), storage and flexibility optimisation.** Awaiting approval.

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

## 3. Files (Batch 5)
configs/scenarios.yaml; energy_futures/{ingest/fes.py, scenarios/fes.py, scenarios/profiles.py, scenarios/engine.py, scenarios/stress.py, experiments/scenarios.py}; tests/test_scenarios.py; docs/assumptions.md; docs/results/scenarios_report.md; docs/figures/b5_*.png. Package moved from src/energy_futures to energy_futures (D-029).

## 3-4. Files (Batch 4)
configs/advanced.yaml; src/energy_futures/{ingest/benchmarks.py, clean/benchmarks.py, features/build.py, forecast/gbm.py, uncertainty/calibration.py, experiments/advanced.py, experiments/advanced_report.py}; evaluate/backtest.py (run_multi); tests/test_batch4.py; docs/results/forecasting_report.md; docs/figures/b4_*.png.

## 3a. Files (Batch 3)
configs/baselines.yaml; src/energy_futures/{features/calendar.py, forecast/task.py, forecast/baselines.py, evaluate/metrics.py, evaluate/backtest.py, experiments/baselines.py}; tests/test_forecast_task.py; docs/results/baselines_validation.md; docs/figures/*.png.

## 3b. Files (Batch 2)
configs/data.yaml; src/energy_futures/{config.py, pipeline.py, ingest/*, clean/*}; tests/test_clean_demand.py, tests/test_weather_align.py; docs/data_dictionary.md; docs/data_quality/quality_report.json; README, DECISIONS, CHANGELOG, EXPERIMENT_LOG.

## 4. Dataset provenance
v1: 298,032 half-hours, 2009-01-01 to 2025-12-31 UTC, no gaps. Config hash e0446e27f33da46a, manifest hash 31c6628cede87de2. NESO Open Data Licence; Open-Meteo CC BY 4.0 (non-commercial free tier). Data files are git-ignored; rebuild with `pipeline all`.

## 5. Experiments and results
**EXP-005 (scenarios):** Holistic peak +13.9 GW by 2035 / +57.3 GW by 2050 vs 2024 (FES +16.0 / +61.7). Cold, still week 2050: peak net 81.6 GW, 10.1 TWh in 7 days. 30% unmanaged EV charging: +11 GW on the 2035 peak.
**EXP-004 (test 8 Mar 2024–Dec 2025, MAE in MW):** LightGBM FW 664 on underlying demand (naive 1281, linear 1089); on ND, ours 995 vs **NESO 653**. CQR coverage 48.8/79.6/90.5 for 50/80/90%.
**EXP-001 (validation 2023, MAE in MW):** naive_d7 1316 · naive_d2 2302 · linear_calendar 1124 · linear_weather_PW 1089 (perfect-weather). Weather cuts high-demand MAE by 28%. The linear models lose to naive_d7 in Jun–Aug. Older training data adds over-forecast bias. Test set sealed.
Descriptive facts: ND annual mean 35.9 → 26.2 GW and underlying demand 36.6 → 30.2 GW (2009 → 2025); daily temperature–demand correlation −0.78 (2019).

## 6. Tests
59 passed (Batch 5, Claude's workspace). 50 passed (Batch 4). 45 passed natively on macOS (Batch 3 code). Earlier: 26 passed (Claude's sandbox on the Mac, 2026-11-18). Batch 1's 13 tests were verified natively on macOS.

## 7. Problems and open questions
- Claude's sandboxes can't reach NESO or Open-Meteo, so downloads run on Dani's Mac (D-013).
- Scenario EV profile is idealised (D-033): it doesn't match FES EV-at-peak. Offshore wind uses the embedded-wind shape (A8).
- macOS `.venv` issue resolved: 45 tests passed natively without PYTHONPATH (D-016).
- Batch 4 was computed in Claude's cloud workspace. On the Mac, outputs/ must be regenerated with `uv run python -m energy_futures.experiments.advanced validation` then `test` (~35 min).
- The forecast gap to NESO is unexplained in detail (only likely causes are listed). Conditional calibration (cold spells) is not assessed.
- Population weighting for weather is deferred (D-012).

## 8. Approved decisions
DECISIONS.md D-001 to D-034.

## 9. Next three tasks
1. Batch 6, Step 37: aggregated storage model (FES battery MW/GWh per pathway, efficiency, SoC limits) as a linear programme (SciPy HiGHS).
2. Batch 6, Steps 38–40: no-intervention reference, deterministic optimisation on point forecasts, scenario/CVaR optimisation on calibrated quantiles; 6-arm design (D-002).
3. Batch 6, Steps 41–42: compare arms on 2024–2025 (real forecasts) and FES 2035 stress weeks; sensitivity; pre-register success criteria first.
