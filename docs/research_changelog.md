# Research change log (improvement phase)

_Every change after the audit (commit 5db4552, verdict B) is recorded here: goal, files, commands, tests, old vs new results, failures, remaining uncertainty._

## Ground rules
- Baseline: tag `v1-audit-baseline` = commit `5db4552`. Return to it with `git checkout v1-audit-baseline`.
- Work happens on branch `improve/phase-b`; `main` stays as audited until Dani approves a merge.
- Original results are frozen in `outputs_archive/v1_5db4552/` with `SHA256SUMS`; new results go to new versioned folders, never over old ones.
- 2026 data (Jan-Oct) is reserved for ONE pre-declared confirmation run, after the improved calibration is frozen. Disclosure: the NESO day-ahead benchmark file already on disk contains 2026 rows; they were loaded in Batch 4 but never used for modelling, and two rows (18 Nov 2026) were printed once while checking the file format.
- Pre-registration seal: **laptop only** (Dani's choice). Write-ups must state that the protocol's timing cannot be verified by outsiders.

## CS-4 Stage 7 · 24 Nov 2026 · Statistical significance tests on frozen results

- **Goal:** Apply DM tests and Holm correction to EXP-004 and EXP-006 frozen results;
  document formally.
- **DM test 1 — LightGBM FW vs naive_d7 (underlying demand, fw window 664 days):**
  FW MAE 664 MW vs naive 1281 MW; DM = −11.67; p < 0.001. FW significantly better.
- **DM test 2 — LightGBM FW vs NESO (ND, fw window 664 days):**
  FW_ND MAE 995 MW vs NESO 653 MW; DM = +17.13; p < 0.001. NESO significantly better.
- **Holm correction on C-vs-B bootstrap CIs (10 tests: 5 settings × 2 stats):**
  Using pre-specified family (H1, H2): H1 (mean cost Historical 2024-25) survives
  correction (p=0.007 < threshold 0.025); H2 (p95 cost) does not (p=0.91).
  Using full conservative family: no test survives (smallest p=0.007 > threshold 0.005).
  Consistent with EXP-006 published finding (D-038).
- **Files:** `docs/results/statistical_tests.md` (new)
- **No data or models changed; all inputs from frozen outputs/advanced/ and outputs/optimisation/.**

## CS-4 Stage 6 · 24 Nov 2026 · CS-3 confirmation protocol (DRAFT)

- **Goal:** Write the CS-3 protocol before any 2026 data is accessed.
- **Selected method:** baseline (§7 selected baseline in CS-2b Stage 4). CS-3 is therefore
  a consistency check, not a test of an improved method.
- **Pass criteria (pre-declared):**
  - Primary 1: 2026-Q1 overall Coverage_90 ∈ [87%, 95%]
  - Primary 2: 2026-Q1 high-demand Coverage_90 ∈ [75%, 100%]
- **Status:** DRAFT committed. Requires Dani's decision to initiate (download 2026 data).
- **Files:** `docs/cs3_protocol.md` (new)

## CS-2b Stage 5 · 24 Nov 2026 · Conditional calibration results report

- **Goal:** Write rolling evaluation results and selection decision.
- **Key findings:** Baseline retained. Pooled cold Coverage_90: baseline 86.3%, best
  candidate (width_normalised) 88.3% (+1.99 pp; needed ≥ 3.0 pp). 2024-Q4 cold
  coverage 62.5% (baseline) — worst quarter. High-demand fallback = 100% in most
  quarters (< 20 high-demand days per 365-day window). Cloud-vs-Mac: mean diff ≈ 0,
  raw Coverage_90 identical (75.15%).
- **Files:** `docs/results/conditional_calibration.md` (new)

## CS-2b Stages 3d-3f · 24 Nov 2026 · Option D: single Mac FW series

- **Goal:** Replace the cloud-generated FW quantile file with a single consistent
  Mac-generated series for 2024-01-01..2025-12-31, used for both calibration and
  evaluation. This resolves the 67-day gap AND the cloud/Mac architecture inconsistency
  discovered in the STAGE 3b determinism check (113 MW diff, LightGBM parallelism).
- **Stage 3d:** §12 addendum appended to `docs/cs2_preregistration.md` — documents
  determinism failure and new resolution; updates sanity check tolerance to 1.0 pp.
  Committed before any run.
- **Stage 3e:** `regenerate_fw_quantiles.py` updated to save FULL Mac series
  (2024-01-01..2025-12-31) to `outputs/v2_cs2_rolling/inputs/quantiles_FW_raw_mac_2024-2025.parquet`
  and write `outputs/v2_cs2_rolling/inputs/cloud_vs_mac.csv`. Script run time: 388.5 s.
  cloud_vs_mac stats (2024-03-08+ rows): mean abs diff ≈ 0.0 MW for all quantiles; max = 113 MW
  (isolated outlier); raw Coverage_90 identical cloud vs Mac (75.15%). Does not touch
  `outputs/advanced/`.
- **Stage 3f:** `conditional_calibration.load_development_data()` updated to use Mac series;
  `SANITY_TOL_PP` updated to 1.0 in `cs2_rolling_eval.py`; new test added. 110 tests pass.
- **Scripts committed at run time:** 304b7d8

## CS-2b Stage 3 (re-run) · 24 Nov 2026 · Sanity check PASSED

- **Command:** `uv run python energy_futures/experiments/cs2_rolling_eval.py`
- **Script commit at run time:** 304b7d8  |  Mac series commit: 304b7d8
- **Sanity check result:**

  | Period | CS-1 reference | CS-2b baseline | Difference |
  |--------|---------------|----------------|------------|
  | 2023 | 92.5% | 92.47% | −0.03 pp (not a failure condition) |
  | 2024-03-08..2025-12-31 | 90.5% | 90.51% | **+0.01 pp — PASS** |

- **selected_method:** baseline (§7 selection, see Stage 4 entry below)
- **Outputs written:** `outputs/v2_cs2_rolling/metrics_by_quarter.csv`,
  `metrics_pooled.csv`, `data_quality_counts.csv`, `fallback_report.csv`,
  `sanity_check.txt` (PASS), `selection.txt`
- **Data quality:** 0 NaN-y rows dropped across all 11 quarters; 0 NaN-proxy days.

## CS-2b Stage 4 · 24 Nov 2026 · Method selection (§7): baseline retained

- **Result:** No candidate passed all four pre-registered selection rules.
- **Pooled metrics (11 quarters combined):**

  | Method | Coverage_90 all | Coverage_90 cold | Coverage_90 high | Width_90 MW | Winkler MW |
  |--------|----------------|-----------------|-----------------|-------------|------------|
  | baseline         | 91.1% | 86.3% | 85.8% | 2960 | 3694 |
  | mondrian         | 90.3% | 87.6% | 85.7% | 2879 | 3689 |
  | mondrian_extended| 90.2% | 85.5% | 85.4% | 2870 | 3692 |
  | width_normalised | 90.9% | 88.3% | 88.0% | 3099 | 3781 |

- **Rule-by-rule elimination:**
  - **Mondrian:** Rule 2 fails — cold coverage 87.59% < baseline cold 86.26% + 3 = 89.26% (improvement only +1.33 pp; needs ≥ 3.0 pp)
  - **Mondrian_extended:** Rule 2 fails — cold coverage 85.46% < 89.26% (actually −0.80 pp below baseline; fallback dominates for cold days when stratum has < 20 days)
  - **Width_normalised:** Rule 2 fails — cold coverage 88.25% < 89.26% (improvement +1.99 pp; needs ≥ 3.0 pp). Rule 3 also fails: high_demand 88.05% < 85.81% + 3 = 88.81%.
- **Why mondrian/extended fail:** Fallback report shows mondrian falls back to global correction 50-100% of cold days in most quarters (< 20 cold days in 365-day rolling window). Mondrian_extended cold coverage is below baseline, likely because mixing 2022-23 (observed-temperature proxy) and 2024-25 (forecast-temperature proxy) cold days degrades the strata-specific calibration.
- **Conclusion:** Baseline retained. No confirmation run (CS-3) is needed with an improved method.
- **No pre-registered thresholds or methods were changed.**

## CS-2b Stage 3 · 24 Nov 2026 · SANITY CHECK FAILED — evaluation stopped

- **Goal:** Run `cs2_rolling_eval.py` once on real data and check sanity.
- **Command:** `uv run python energy_futures/experiments/cs2_rolling_eval.py`
- **Script commit at run time:** 7a073ce (CS-2b stage 2b)
- **Runtime:** 27.1 s
- **Result:** STOPPED — sanity check raised ValueError before writing selection.txt.
- **Sanity check output:**

  | Period | CS-1 reference | CS-2b baseline | Difference |
  |--------|---------------|----------------|------------|
  | 2023 (all HH) | 92.5% | 92.47% | −0.03 pp (not a failure condition) |
  | 2024-03-08 to 2025-12-31 | 90.5% | **88.51%** | **−1.99 pp (exceeds ±0.5 pp tolerance)** |

- **Root cause identified (not a code bug):** The original EXP-004 CQR calibration used
  `Q = pd.concat([q23, qp[k]])` where `qp[k]` covered the full test period from
  2024-01-01; only the slice from `fw0 = "2024-03-08"` onward was saved as
  `quantiles_FW_raw.parquet`. CS-2b's `load_development_data()` loads this file and
  `quantiles_2022_2023.parquet` (ending 2023-12-31), leaving a **67-day gap** in
  raw_q (2024-01-01 to 2024-03-07). Those winter months carry high nonconformity scores;
  their absence from the calibration window reduces the CQR correction level and therefore
  coverage for 2024-25 days. The 2023 baseline matches CS-1 exactly (−0.03 pp), confirming
  the calibration code itself is correct.
- **Partial outputs written (before sanity check):** `outputs/v2_cs2_rolling/metrics_by_quarter.csv`,
  `metrics_pooled.csv`, `data_quality_counts.csv`, `fallback_report.csv`.
  `selection.txt` was NOT written (guard worked as designed).
- **Decision needed from Dani — two options (neither changes a pre-registered method):**
  1. **(Preferred)** Re-generate `quantiles_FW_raw.parquet` from 2024-01-01 by re-running
     `uv run python -m energy_futures.experiments.advanced test` — this restores the original
     calibration history. The model is already trained; re-running test() only re-applies
     quantile prediction and rolling CQR, it does not retune any model.
  2. **Alternatively**, update `load_development_data()` to also load the Q1-2024 slice
     by extracting it from the full advanced.py pipeline (would require a new data file).
- **Stages 4–7 are deferred pending resolution.**
- **No 2026 data accessed. No pre-registered methods changed.**

## CS-2b stage 2b · 24 Nov 2026 · Eval script fixes before run

- **Goal:** Harden `cs2_rolling_eval.py` before the first real data run; add three improvements
  pre-committed as pre-registration (no results seen yet).
- **Files modified:**
  - `energy_futures/experiments/cs2_rolling_eval.py` — three additions (a–c):
    - **(a) NaN y handling:** `_add_hh_metrics` now drops half-hours with missing actual demand
      before computing any metric. Count of dropped half-hours reported per quarter and method in
      `data_quality_counts.csv` (renamed from `nan_proxy_counts.csv`; also retains
      `n_nan_proxy_days`).
    - **(b) Sanity check in `run()`:** `_sanity_check()` function computes baseline Coverage_90 on
      2024-03-08..2025-12-31 (expected ≈90.5%) and on 2023 (expected ≈92.5%); writes
      `sanity_check.txt` with CS-1 reference values alongside CS-2b values; raises `ValueError`
      if the 2024-25 value differs from 90.5% by more than 0.5 pp. `selection.txt` is written
      by `run()` only AFTER the sanity check passes (i.e. `evaluate()` no longer writes it).
    - **(c) Fallback report (reporting only):** `_compute_fallback_summary()` computes, for each
      evaluation day, whether mondrian and mondrian_extended fell back to the global correction
      (stratum count < 20 days in window); `_fallback_by_quarter()` aggregates to per-quarter
      per-stratum share; written to `fallback_report.csv`. No calibration is changed.
  - `tests/test_cs2_rolling_eval.py` — 10 new tests covering (a)–(c):
    - `test_nan_y_dropped_before_metrics`, `test_nan_y_no_effect_when_zero`
    - `test_sanity_check_passes`, `test_sanity_check_fails_on_large_deviation`,
      `test_sanity_check_2023_not_a_failure`, `test_sanity_check_nan_raises`,
      `test_sanity_data_in_result`
    - `test_fallback_report_exists`, `test_fallback_shares_in_range`,
      `test_fallback_extended_cold_le_mondrian_cold`
    - Existing tests updated for renamed file (`data_quality_counts.csv`) and removed
      `selection.txt` from `evaluate()` assertions.
- **Tests:** `uv run pytest -q` → 109 passed, 0 failed.
- **No evaluation run.** No 2026 data accessed.

## CS-2b · 24 Nov 2026 · Rolling evaluation script + strengthened test (committed before any run)

- **Goal:** Pre-register the evaluation script (CS-2b) and strengthen the baseline-match test
  before any real evaluation is run.
- **Files added:**
  - `energy_futures/experiments/cs2_rolling_eval.py` — evaluation script committed before any run:
    loads development data; applies all four methods over 2023-01-01 to 2025-12-31 with
    window_days=365 from EVAL_START; computes §6 metrics (Coverage_90/80/50 overall, cold
    proxy-based, high-demand §6.1, winter, bank holiday, and outcome-based cold labelled
    "reporting only"; Width_90; Winkler; Pinball); block-bootstrap 95% CIs by calendar day,
    1,000 resamples, seed 42; NaN-proxy day counts per quarter; calls select_method on pooled
    results; writes to outputs/v2_cs2_rolling/ only.
  - `tests/test_cs2_rolling_eval.py` — 3 end-to-end tests on synthetic data:
    - `test_evaluate_smoke` — files written, return dict well-formed, all 4 methods present.
    - `test_evaluate_nan_proxy_counted` — NaN proxy days reported correctly per quarter.
    - `test_evaluate_high_demand_threshold_consistent` — high-demand n_days identical across
      methods (threshold uses raw q50 over the full window, same for all methods).
- **Files modified:**
  - `tests/test_conditional_calibration.py` — `test_baseline_matches_rolling_cqr` strengthened:
    now uses seeded random quantiles and actuals (not constant), 75 days crossing the 2023-03-26
    BST spring-forward (clock change), window_days=30. Asserts exact match (decimal=8).
    Sanity assertion: window_days=29 on the baseline side vs window_days=30 on the rolling_cqr
    side produces different output, confirming the test can detect a wrong window size.
- **Tests:** `uv run pytest -q` → 99 passed, 0 failed.
- **No evaluation run.** No 2026 data accessed. outputs_archive/ untouched.
- **Remaining uncertainty:** `cs2_rolling_eval.evaluate()` has not been run on real data yet.
  Correctness will be verified in CS-2b run (requires Dani's approval).

## CS-2a review · 24 Nov 2026 · Amendment clarification + 5 new tests

- **Goal:** Pre-registration clarification and additional tests following CS-2a review.
- **Files changed:**
  - `docs/cs2_preregistration.md` — appended "Amendment 1 clarification" under §11:
    W_t spans start ≤ train_cutoff (08:00 D-1) and > cutoff − 365 days; "ends at D-2"
    referred only to complete calendar days (temperature proxy); NaN proxy → not cold,
    NaN-proxy day count reported per quarter.
  - `tests/test_conditional_calibration.py` — 5 new tests added:
    - `test_no_lookahead_all_methods` — actuals after 08:00 D-1 cutoff do not affect
      day D's calibrated interval, for all four methods.
    - `test_baseline_matches_rolling_cqr` — apply_calibration_daily baseline reproduces
      the existing rolling_cqr output on the same synthetic input.
    - `test_mondrian_extended_uses_and_falls_back` — Candidate C uses cold scores from
      outside the standard window when ≥20 past cold days exist; falls back to global
      when fewer than 20.
    - `test_load_development_data_2026_guard` — raises ValueError when a 2026 timestamp
      is present in the quantile data.
    - `test_nan_temp_proxy_never_cold` — NaN temperature proxy is never classified "cold".
  - `energy_futures/experiments/conditional_calibration.py` — one-line bug fix:
    `day_ts = pd.Timestamp(day)` (tz-naive) instead of `pd.Timestamp(day, tz=TZ)`;
    `task.train_cutoff` calls `tz_localize` internally and requires a tz-naive input.
- **Tests:** `uv run pytest -q` → 96 passed, 0 failed (14 in test_conditional_calibration.py).
- **No evaluation run.** No 2026 data accessed.

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
