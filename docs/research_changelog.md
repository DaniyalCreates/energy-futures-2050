# Research change log (improvement phase)

_Every change after the audit (commit 5db4552, verdict B) is recorded here: goal, files, commands, tests, old vs new results, failures, remaining uncertainty._

## Ground rules
- Baseline: tag `v1-audit-baseline` = commit `5db4552`. Return to it with `git checkout v1-audit-baseline`.
- Work happens on branch `improve/phase-b`; `main` stays as audited until Dani approves a merge.
- Original results are frozen in `outputs_archive/v1_5db4552/` with `SHA256SUMS`; new results go to new versioned folders, never over old ones.
- 2026 data (Jan-Oct) is reserved for ONE pre-declared confirmation run, after the improved calibration is frozen. Disclosure: the NESO day-ahead benchmark file already on disk contains 2026 rows; they were loaded in Batch 4 but never used for modelling, and two rows (18 Nov 2026) were printed once while checking the file format.
- Pre-registration seal: **laptop only** (Dani's choice). Write-ups must state that the protocol's timing cannot be verified by outsiders.

## CS-2a · 24 Nov 2026 · Conditional calibration method code

- **Goal:** Implement all four calibration methods from the CS-2 pre-registration.
  Code committed before any evaluation is run (CS-2b).
- **Files added:**
  - `energy_futures/experiments/conditional_calibration.py`
  - `tests/test_conditional_calibration.py`
- **Functions implemented:**
  - `load_development_data()` — loads both quantile files and builds temp proxy
    (D-2 observed for 2022-23, archived forecast for 2024-25); hard 2026 guard.
  - `assign_stratum(day, temp_proxy, max_q50, threshold_95)` — priority: cold → high_demand → normal.
  - `calibrate_baseline(scores_window)` — finite-sample (1-α)(n+1)/n quantile.
  - `calibrate_mondrian(scores_window, strata_window, target_stratum, min_days=20)` — stratum-specific
    correction; falls back to global if fewer than 20 stratum calendar days (approximated as n//48).
  - `calibrate_width_normalised(norm_scores_window)` — same level formula on normalised scores.
  - `apply_calibration_daily(raw_quantiles, actuals, temp_series, method, window_days=365)` — daily
    rolling calibration for all four methods; restores quantile monotonicity.
  - `select_method(results_dict)` — applies §7 rules in order; returns "baseline" if none qualify.
- **Tests:** 9 tests in `test_conditional_calibration.py`; `uv run pytest -q` → 91 passed.
- **No evaluation run.** No 2026 data accessed. No existing files modified.
- **Remaining uncertainty:** `apply_calibration_daily` has not been run on real data yet.
  Correctness will be verified in CS-2b.

## CS-2 pre-registration Amendment 1 · 24 Nov 2026 · Timing correction

- **Goal:** Correct a timing error in the pre-registration before any CS-2 code is written.
- **What changed:** Appended `## 11. Amendment 1` to `docs/cs2_preregistration.md`.
  - W_t now ends at D-2 (last fully observed day at issue time 09:00 D-1), not D-1.
  - 2022-23 temperature proxy is D-2 observed GB daily mean, not D-1 observed.
  - Overrides §3, §4, §5 where they conflict.
- **Reason:** External review identified that `task.train_cutoff(D)` = 08:00 local D-1,
  meaning D-1 is only partially observed at issue time; last full day is D-2.
- **No code written or run.** No results changed. `docs/cs2_preregistration.md` only.

## CS-1 · 21 Nov 2026 · Coverage diagnostic report

- **Goal:** Measure empirical coverage of the existing 50/80/90% CQR prediction intervals broken down by operating condition (cold days, winter, bank holidays, Christmas, top-5% demand, time of day, month, year). Diagnostic only — no new methods, no 2026 data.
- **Data sources (read-only):**
  - `outputs/advanced/validation/quantiles_2023_cqr.parquet` (2023 validation, 17,520 rows)
  - `outputs/advanced/test/quantiles_FW_cqr.parquet` (2024-25 test, 31,872 rows)
  - `data/processed/demand_weather.parquet` (actual demand + observed temperatures)
  - `data/raw/weather_forecast/*.json` (archived ~48 h-ahead forecast temperatures, 2024-25 only)
- **Commands:**
  - `uv run python energy_futures/experiments/coverage_diagnostics.py`
  - `uv run pytest -q` (82 passed, 0 failed; +13 new tests)
- **New files:**
  - `energy_futures/experiments/coverage_diagnostics.py`
  - `tests/test_coverage_diagnostics.py`
  - `outputs/v2_cs1_coverage/coverage_conditions.csv`
  - `outputs/v2_cs1_coverage/coverage_by_month.csv`
  - `outputs/v2_cs1_coverage/coverage_by_year.csv`
  - `outputs/v2_cs1_coverage/coverage_by_hour.csv`
  - `docs/results/coverage_diagnostics.md`
- **No existing files modified.** `outputs_archive/v1_5db4552/` untouched.
- **Results (90% nominal interval; block-bootstrap 95% CI by day, 1,000 resamples, seed 42):**

  | Period | Condition | Coverage % | CI low % | CI high % |
  |---|---|---|---|---|
  | 2023 | All | 92.47 | 90.99 | 93.79 |
  | 2023 | Cold (observed < 3 °C) | 93.28 | 90.62 | 95.74 |
  | 2023 | Winter (Dec–Feb) | 89.56 | 86.18 | 92.45 |
  | 2024-25 | All | 90.51 | 89.39 | 91.62 |
  | 2024-25 | Cold (observed < 3 °C) | **80.32** | 70.75 | 88.35 |
  | 2024-25 | Cold (forecast < 3 °C) | **82.58** | 72.83 | 90.25 |
  | 2024-25 | Winter (Dec–Feb) | 87.00 | 83.75 | 90.07 |
  | 2024-25 | Bank holiday | 84.58 | 73.06 | 93.89 |
  | 2024-25 | Christmas period | 86.57 | 76.39 | 94.10 |
  | 2024-25 | Top-5% demand days | **82.48** | 74.14 | 89.77 |
  | 2024 (Mar–Dec) | All | 92.26 | 90.44 | 93.89 |
  | 2025 (full year) | All | **89.07** | 87.71 | 90.50 |

  Overall coverage matches EXP-003/004 record to within 0.1 pp (rounding from different aggregation method).

- **Key finding:** Coverage is well-calibrated overall and in 2023. In 2024-25, the intervals are undercovering on cold days (~80%, CI entirely below nominal 90%), top-5% demand days (~82%), Christmas/bank holidays (~85-87%), and in 2025 as a whole (~89%, CI barely touching 90%). The problem is conditional on hard, high-demand conditions — exactly the conditions that matter for battery scheduling.
- **Failures / anomalies:** None. Script ran cleanly.
- **Remaining uncertainty:**
  - Only 22-27 cold days per period — CIs are wide; the gap could be partly sampling noise.
  - Cold-day threshold (3 °C, equal-weight GB mean) is a simplification (D-012 defers population weighting).
  - Bootstrap CI assumes independent blocks; seasonal correlation within periods may make CIs slightly too narrow.
  - 2024 covers only March–December (forecast radiation archive constraint).
  - Pre-registration seal: laptop only.
- **Recommended next step:** CS-2 — conditionally recalibrate the intervals on cold/high-demand days using the validation period. Candidates: (a) separate CQR calibration sets for cold vs warm days; (b) temperature-stratified conformal scores; (c) temperature as a covariate in the nonconformity score. Decide method before looking at test-period conditional residuals.

## CS-0 · 19 Nov 2026 · Safety baseline
- **Goal:** make every later change reversible and keep original results provably unchanged.
- **Commands:** `git tag -a v1-audit-baseline 5db4552`; `cp -an outputs` and `data/processed` → `outputs_archive/v1_5db4552/`; `sha256sum` list → `SHA256SUMS` (45 files, 37 MB); `git switch -c improve/phase-b`.
- **Note:** the temporary `outputs/transfer/` bundles were removed from the archive *copy* after copying (originals untouched); results files are all archived.
- **Check:** archived dataset fingerprint `66a4d9a0dc66754f` = audited dataset.
- **Files changed:** `.gitignore` (ignore `outputs_archive/`), this log.
