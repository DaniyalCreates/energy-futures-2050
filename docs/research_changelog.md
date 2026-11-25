# Research change log (improvement phase)

_Every change after the audit (commit 5db4552, verdict B) is recorded here: goal, files, commands, tests, old vs new results, failures, remaining uncertainty._

## Ground rules
- Baseline: tag `v1-audit-baseline` = commit `5db4552`. Return to it with `git checkout v1-audit-baseline`.
- Work happens on branch `improve/phase-b`; `main` stays as audited until Dani approves a merge.
- Original results are frozen in `outputs_archive/v1_5db4552/` with `SHA256SUMS`; new results go to new versioned folders, never over old ones.
- 2026 data (Jan-Oct) is reserved for ONE pre-declared confirmation run, after the improved calibration is frozen. Disclosure: the NESO day-ahead benchmark file already on disk contains 2026 rows; they were loaded in Batch 4 but never used for modelling, and two rows (18 Nov 2026) were printed once while checking the file format.
- Pre-registration seal: **laptop only** (Dani's choice). Write-ups must state that the protocol's timing cannot be verified by outsiders.

## Stage 23 · 25 Nov 2026 · README wording fixes before publish

- **Goal:** Three accuracy corrections to README.md requested by Dani before publish.
  (a) Results table: "Yes on average cost (significant)" → "Yes on average cost
      (exploratory secondary finding)" to match D-042 and technical report §5.3.
  (b) Intro: "All experiments are pre-registered" → "The key experiments (forecast test,
      battery study, CS-2, CS-3) were pre-registered" — the baselines and scenario
      experiments were not formally pre-registered.
  (c) New section "How this was built": states AI coding assistance (Claude Code) under
      Dani's direction and that all changes are recorded in the changelog.
- **Tests:** 201 passed.
- **File changed:** `README.md` only.

## Stage 22 · 25 Nov 2026 · Launch preparation: README rewrite, .gitignore, LICENSE, safety scan

- **Goal:** Prepare the repository for publication (not yet pushed).
- **(a) README.md rewritten** for a recruiter audience: 6-line plain-English intro,
  headline results table (forecast MAE vs naive and vs NESO, CS-3 verdict with cold-day
  caveat, battery decision result with significance caveat), reproduce commands, project
  structure table, honest status and limitations pointer, data attribution section.
- **(b) Safety scan findings:**
  - No secrets, API keys, or `.env` files in tracked files. `.env.example` is a benign
    template only.
  - No files over 50 MB.
  - No absolute `/Users/daniyaltariq` paths in Python or YAML files.
  - `CLAUDE.md` (tracked) contains the commit email `tariqdaniyal048@gmail.com` and a
    reference to the path of a separate dissertation project. This becomes public with the
    repo — Dani to decide whether to remove or gitignore before push.
  - `docs/release_checklist.md` also mentions the email in a decision item.
  - `Energy_Futures_2050_Progress_and_Improvement.pdf` was untracked and unignored;
    added `*.pdf` to `.gitignore`.
  - `outputs_archive/` and `data/` are already gitignored; `outputs/` placeholder only
    (.gitkeep); `*.parquet` and `*.csv.gz` already gitignored.
- **(c) Data attribution:** present in README (NESO Open Data Licence, Open-Meteo CC BY
  4.0 with links).
- **(d) LICENSE created:** MIT, Copyright (c) 2026 Daniyal Tariq.
- **(e) Tests:** 201 passed.
- **Upload size:** 1.9 MB across 102 files (code, docs, figures, configs, uv.lock).
  No raw data, processed data, model outputs, or outputs_archive in the upload.

## Stage 21 · 25 Nov 2026 · cs3_confirmation.md wording: Disclosure 2, cold-day caveat, bootstrap detail

- **Goal:** Three wording corrections to `docs/results/cs3_confirmation.md`:
  (a) Disclosure 2 — replace the 0.4 MW AUDIT-001 OLS reference with this project's own
      measurement from CS-2 Amendment 2: mean abs diff ≈ 0.0 MW, max 113 MW, raw
      Coverage_90 identical at 75.15% cloud vs Mac.
  (b) Summary — add explicit cold-day caveat: 84.7%, n=11 coverage is below the 85–95%
      band and is a known weakness; PASS means calibration holds overall and on
      high-demand days, not all conditions equally.
  (c) CI description — clarify the 7-day block bootstrap resamples days (not half-hours),
      with each resampled day contributing all 48 half-hours.
- **File changed:** `docs/results/cs3_confirmation.md` (Disclosures §2, Summary, Criteria §CI).
- **No code changes. No tests changed.**

## Stage 20 · 25 Nov 2026 · CS-3 results documentation

- **Goal:** Write the full CS-3 confirmation report; update technical report §7–§8 and
  PROJECT_STATUS.md; add CS-3 entry to EXPERIMENT_LOG.md; changelog.
- **Files changed:**
  - `docs/results/cs3_confirmation.md` — new file: plain-English summary, verbatim verdict,
    per-criterion table (Coverage_90, n_days, CI, threshold, outcome), four disclosures
    (Batch 4 2026 rows, Mac-only run, timing, Deviation 1), package versions, refit log,
    output files.
  - `docs/technical_report.md` — §7 Limitation 5: added sentence that CS-3 (2026
    confirmation, verdict PASS) partially addresses the single-test-period concern;
    §8 Reproducibility: updated test count to 201, added CS-3 paragraph with full numbers.
  - `PROJECT_STATUS.md` — §5: added CS-3 result line; §6: updated test count to 201;
    §8: updated "D-001 to D-042"; §9: added CS-3 complete note.
  - `EXPERIMENT_LOG.md` — added CS-3 entry after AUDIT-001 with verdict, criteria table,
    environment and runtime.
- **Results (from cs3_verdict.txt):**
  - Co-primary 1 (Jan–Feb Coverage_90): **89.8%**, n=59, [85–95%] → PASS
  - Co-primary 2 (high-demand Coverage_90): **90.9%**, n=17, 95% CI [82.8%, 95.8%], ≥80% → PASS
  - Secondary (Jan–Oct overall): 89.4%, n=304 (expected [88–92%])
  - Cold days (descriptive): 84.7%, n=11
- **No code changes, no new tests.** All 201 existing tests continue to pass.

## Stage 19 · 25 Nov 2026 · CS-3 confirmation run (single execution)

- **Goal:** Execute CS-3 exactly once per approved protocol.
  Stop rules: failure of any download, guard, schema check, or unexpected package version.
- **Execution order:**
  1. `download_all()` — NESO CSV 1.6 MB downloaded; ERA5 all 6 city files downloaded.
     Failed at schema guard (Deviation 1 — see Stage 17 fix entry). Stopped; fix approved.
  2. Stage 17 fix applied and committed (see entry below). Re-ran from processing step
     (raw files already downloaded; not re-downloaded).
  3. `generate_cs3_quantiles.run()` — 4 QS refits with expanding window from 2009:
     Q1 train_end 2025-12-31 (4,318 eval rows), Q2 train_end 2026-03-31 (4,368),
     Q3 train_end 2026-06-30 (4,416), Q4 train_end 2026-09-30 (1,490).
     Output: `outputs/v3_cs3_confirmation/inputs/quantiles_FW_raw_mac_2026.parquet`
     (14,592 rows, q05–q95). Runtime: 201 s.
  4. `cs3_confirmation.run()` — applied calibration, computed criteria. Runtime: 2 s.
     Output: `outputs/v3_cs3_confirmation/cs3_verdict.txt`,
     `outputs/v3_cs3_confirmation/metrics_by_period.csv`,
     `outputs/v3_cs3_confirmation/package_versions.txt`.
- **Package versions (from outputs/v3_cs3_confirmation/package_versions.txt):**
  Python 3.12.16 (Clang 23.1.3, arm64), lightgbm 4.7.0, numpy 2.5.5, pandas 3.1.1,
  macOS-15.7.7-arm64. All versions within those specified in `docs/cs3_protocol.md`.
- **Verdict: PASS** (see Stage 20 for full numbers).
- **No re-run after results seen.** Single execution as specified.

## Stage 17 fix · 25 Nov 2026 · Bug fix: keep all weather columns; reorder before saving (Deviation 1)

- **What happened:** Stage 19's first `download_all()` call failed at the schema guard
  after NESO CSV (1.6 MB) and all 6 ERA5 city files downloaded successfully.
  Stage 14's `_build_demand_weather_2026` filtered weather to `_gb_mean` only;
  reference `demand_weather.parquet` has both per-city and gb_mean columns (46 total vs 22).
- **Fix (approved by Dani):**
  - `_build_demand_weather_2026`: removed `gb_cols` filter; changed to `demand.join(wx)`.
  - New helper `_reorder_columns_to_reference(df, reference, context)`: raises if column
    sets differ; reorders df columns to match reference order exactly. Called before
    `_check_schema_match` and before saving.
  - Deviation 1 note appended to `docs/cs3_protocol.md` (§ Deviations).
- **New tests in `tests/test_download_cs3_data_2026.py`** (4 new, `TestReorderColumnsToReference`):
  - wrong-order columns are reordered; missing column raises; extra column raises;
    reorder then schema-check passes.
- **No method, threshold or criterion changed.**
  The error message printed column names only (no demand values, row counts, or statistics).
- **Test count:** 197 → 201 passed.

## Stage 17 · 25 Nov 2026 · Two pre-run safety fixes: ERA5 completeness guard; schema check before concatenation

- **Goal:** Harden the data pipeline so a partial or mismatched 2026 build raises an
  error immediately rather than silently producing a demand-only or type-mismatched
  parquet that would corrupt the CS-3 quantile run.
- **Fix (a) — ERA5 completeness guard (`download_cs3_data_2026.py`):**
  - New function `_check_era5_files_complete(raw_weather_dir=None)`: verifies that all 6
    expected city files (`{city}_2026.json`) exist in `RAW_WEATHER_DIR` and that each
    contains all 4 `HOURLY_VARS` keys.  Raises `RuntimeError("missing")` or
    `RuntimeError("incomplete")` on failure.
  - `_build_demand_weather_2026`: replaced the `if era5_files: ... else: WARNING`
    block with an unconditional call to `_check_era5_files_complete()`. Demand-only
    output is no longer possible.
- **Fix (b) — schema check before concatenation:**
  - New function `_check_schema_match(candidate, reference, context)` added to both
    `download_cs3_data_2026.py` and `generate_cs3_quantiles.py`.  Raises
    `RuntimeError("Schema mismatch")` if columns differ, `RuntimeError("Dtype mismatch")`
    if any column's dtype differs.
  - `_build_demand_weather_2026`: calls `_check_schema_match(merged, ref, ...)` after
    building `merged`, using `demand_weather.parquet` as the reference (skips if that
    file is absent; in practice it always exists).
  - `load_combined_demand` in `generate_cs3_quantiles.py`: calls `_check_schema_match`
    before `pd.concat`, so the error is caught before any training data is loaded.
  - Also added `DEMAND_HIST_PATH` constant to `download_cs3_data_2026.py`.
- **New tests:** 10 total (197 passing):
  - `TestEra5FilesComplete` (4): all missing; one missing; last file incomplete
    (variable absent); all complete passes.
  - `TestSchemaMatchDownload` (3): matching passes; extra column raises; dtype mismatch raises.
  - `TestLoadCombinedDemandSchemaCheck` (3): extra column in 2026 raises; dtype mismatch raises;
    matching schemas concatenate correctly and return correct row count.
- **No 2026 data downloaded or opened.**

## Stage 16 · 25 Nov 2026 · Restore DECISIONS.md D-038; add D-042; tidy cs3_protocol.md §4

- **Goal:** Restore D-038 to its original Batch 6 wording (Stage 11 had modified it
  in-place instead of adding a correction row). Add D-042 as the correction row.
  Tidy §4 of cs3_protocol.md to replace an outdated prohibition.
- **DECISIONS.md — D-038 restored:**
  Original wording (Batch 6, pre-Stage 11): "Verdict: H1 and H3 met on point estimates,
  but tail-metric gains are not statistically significant; mean-cost gain is significant.
  The KTP claim is limited accordingly"
  Stage 11 had changed this in-place; now reverted to above.
- **DECISIONS.md — D-042 added (new row):**
  `| D-042 | 2026-11-25 | Correction to D-038: H1 as pre-registered (p95 AND shortfall
  AND mean ≤ B+1%) is not statistically supported; the mean-cost gain is an exploratory
  secondary finding (statistical_tests.md §3.4). |`
- **docs/cs3_protocol.md §4 — wording tidied:**
  Replaced: "No code changes are permitted before running CS-3."
  With: "No changes to method code; the wrapper and data scripts listed here must be
  committed before approval."
  (The wrapper and download scripts are now committed; this wording matches reality.)
- **No code changes.** No tests changed. No 2026 data downloaded.
- **Files:** `DECISIONS.md`, `docs/cs3_protocol.md`

## Stage 15 · 25 Nov 2026 · Fix cs3_confirmation.py: raw q50 for hd selection, bootstrap CI, n_days, demand guard, weather error

- **Goal:** Five targeted corrections to `cs3_confirmation.py` identified in review; tests for each.
- **Change 1 — high-demand day selection uses RAW q50 (protocol §6):**
  `compute_criteria` now accepts `raw_q: pd.DataFrame | None = None`. When provided,
  `_q_for_hd["q50"].groupby(local_dates).max()` uses `raw_q` instead of `cal_q` for the
  high-demand day threshold comparison. `run()` extracts `raw_q_eval` from the loaded
  `q2026` (pre-calibration quantiles) and passes it.
- **Change 2 — 95% block-bootstrap CI for co-primary 2:**
  New function `_block_bootstrap_ci_coverage(cal_q, y, hd_dates, block_size=7, n_boot=1000,
  seed=42)` resamples by day (moving block bootstrap on sorted high-demand dates). Called
  inside `compute_criteria`; result keys `ci_high_demand_lo` and `ci_high_demand_hi`
  added to the result dict.
- **Change 3 — n_days reported for all periods:**
  `compute_criteria` now returns `n_days_jan_feb` (unique local days in Jan-Feb window)
  and `n_days_jan_oct` (unique local days in full window). `_write_outputs` uses them
  in `metrics_by_period.csv` and `cs3_verdict.txt`.
- **Change 4 — date guard applied to 2026 demand file:**
  `run()` now calls `_date_guard(demand_2026)` immediately after loading the demand
  parquet (before extracting `y_2026`).
- **Change 5 — raise FileNotFoundError on missing weather file:**
  `_load_forecast_temp_2026()` now raises `FileNotFoundError` if any city JSON is absent,
  instead of silently returning an empty Series.
- **New tests in `tests/test_cs3_confirmation.py`** (22 new, 35 total new):
  - `TestHighDemandUsesRawQ50` (2): raw q50 above threshold → hd days selected;
    raw q50 below threshold → 0 hd days even when cal_q is high.
  - `TestBlockBootstrapCI` (4): perfect coverage → CI ≈ [100,100]; empty hd_dates → (nan,nan);
    partial coverage → lo ≤ hi; compute_criteria includes ci keys.
  - `TestNDaysReporting` (2): n_days_jan_feb = 59; n_days_jan_oct = 304.
  - `TestDateGuardOnDemandDataFrame` (2): demand df with Nov 2026 raises; valid range passes.
  - `TestMissingWeatherFileRaises` (1): raises FileNotFoundError when file absent.
  - Updated `test_result_contains_required_keys` to check all new keys.
- **Test count:** 176 → 187 passed.
- **No 2026 data downloaded or opened.**

## Stage 14 · 25 Nov 2026 · CS-3 download and quantile-generation scripts (write-only; no 2026 data accessed)

- **Goal:** Write (but not run) the scripts that will download 2026 data and generate CS-3 quantiles once Dani approves the protocol. All network calls mocked in tests; no 2026 files downloaded or opened.
- **New file: `energy_futures/experiments/download_cs3_data_2026.py`**
  - `demand_2026()`: downloads NESO historic demand 2026 CSV via CKAN API and ERA5
    actual weather for 6 cities (2026-01-01..2026-10-31); produces
    `data/processed/demand_weather_2026.parquet`.
  - `forecast_weather_2026()`: downloads Open-Meteo Previous Runs API
    (`previous_day2`) for 6 cities, 2026-01-01..2026-10-31; writes
    `data/raw/weather_forecast/{city}_2026.json`.
  - `download_all()`: runs both in order. All calls restricted to CS3_START..CS3_END.
  - Helper `_get_with_retry(url, params, n_retry=4)`: handles 429 rate-limiting with
    linear backoff (30 s × attempt).
  - Helper `_write_manifest()`: appends SHA256, URL, timestamp to `data/raw/manifest.csv`.
- **New file: `energy_futures/experiments/generate_cs3_quantiles.py`**
  - `load_combined_demand(demand_path, demand_2026_path)`: concatenates 2009-2025
    and 2026 parquets so Jan 2026 half-hours draw on Dec 2025 lag values (no year
    boundary gap).
  - `_check_output_dates(q)`: raises ValueError if any output row falls outside
    2026-01-01..2026-10-31.
  - `run(...)`: loads validation summary → start_pw; loads combined demand + archived
    forecast weather; builds PW and FW feature sets;
    calls `backtest.run_multi(lambda: GBMQuantile(True, start_pw), X_pw, y, {"FW": X_fw},
    CS3_START, CS3_END, "QS", method="predict_quantiles")`; validates output dates;
    writes `outputs/v3_cs3_confirmation/inputs/quantiles_FW_raw_mac_2026.parquet`.
- **New file: `tests/test_download_cs3_data_2026.py`** (12 tests; all network mocked)
  - `TestNesoListResources` (3): parses year/url from CKAN JSON; excludes non-CSV;
    missing year not in result.
  - `TestGetWithRetry` (3): success on 200; raises RuntimeError after max retries on 429;
    retries on 429 then succeeds.
  - `TestForecastWeather2026DateGuard` (1): params use CS3_START/CS3_END exactly.
  - `TestEra5Weather2026DateGuard` (1): params use CS3_START/CS3_END exactly.
  - `TestConstants` (4): cs3 window is 2026; 6 locations; forecast vars match pipeline;
    lead is `previous_day2`.
- **New file: `tests/test_generate_cs3_quantiles.py`** (12 tests; no LightGBM training)
  - `TestLagFeatureContinuity` (4): lag_d2 not NaN when Dec 2025 history present;
    lag_d7 not NaN; lag_d2 IS NaN when no Dec 2025 history; combined index has no duplicates.
  - `TestCheckOutputDates` (4): valid range passes; Nov 2026 raises; mixed raises;
    Oct 31 exactly passes.
  - `TestRefitCutoffOrdering` (4): all QS cutoffs < block_start; Q1-2026 train_cutoff
    is in year 2025; blocks cover full 2026-01-01..2026-10-31; exactly 4 QS refits.
- **Tests:** 24 new tests; all pass. **Total test count: 152 → 176 passed.**
- **No 2026 data downloaded or opened.** MUST NOT run download_all() or run()
  until Dani approves docs/cs3_protocol.md.

## Stage 13 · 25 Nov 2026 · cs3_confirmation.py and tests (synthetic data only)

- **Goal:** Write `energy_futures/experiments/cs3_confirmation.py` and
  `tests/test_cs3_confirmation.py` and commit BEFORE any 2026 data download
  (required by cs3_protocol.md §4, as corrected in Stage 12).
- **Script: `energy_futures/experiments/cs3_confirmation.py`** (new)
  - `_date_guard(raw_q)`: raises ValueError if any 2026 rows fall outside
    2026-01-01..2026-10-31. Called before any evaluation.
  - `_load_forecast_temp_2026()`: loads archived forecast temp from
    `data/raw/weather_forecast/{city}_2026.json`; returns empty Series if files
    not found (not yet downloaded). 2026 guard applied to dates.
  - `coverage_90(cal_q, y, mask=None)`: Coverage_90 as a percentage.
  - `_make_verdict(...)`: applies §8 pass criteria:
    - Co-primary 1: cov_jan_feb ∈ [85%, 95%]
    - Co-primary 2: cov_hd ≥ 80% (requires n_hd ≥ 5; else INCONCLUSIVE)
    - Returns (verdict, reasons): "PASS" / "FAIL" / "MIXED" / "INCONCLUSIVE"
  - `compute_criteria(cal_q, y, temp_proxy)`: computes all §8 metrics and verdict.
  - `run(...)`: full pipeline — loads historical calibration data, 2026 quantiles,
    2026 actuals; calls `apply_calibration_daily(..., method="baseline", ...)`;
    restricts to 2026-01-01..2026-10-31; writes cs3_verdict.txt,
    metrics_by_period.csv, package_versions.txt to `outputs/v3_cs3_confirmation/`.
    **Not to be called until Dani approves the protocol.**
- **Tests: `tests/test_cs3_confirmation.py`** (new, 28 tests; synthetic data only)
  - `TestDateGuard` (5): valid range, no-2026 rows, Nov 2026 raises, mixed hist+2026,
    mixed valid+invalid 2026 raises.
  - `TestCoverage90` (6): 100%, 0%, 50%, mask restriction, empty mask → NaN,
    all-NaN actuals → NaN.
  - `TestMakeVerdict` (8): both pass, jan-feb fail, hd fail → MIXED, both fail,
    jan-feb over 95% → fail, n_hd<5 → INCONCLUSIVE, NaN jan-feb → INCONCLUSIVE,
    reasons contain values.
  - `TestComputeCriteria` (9): 100% coverage (over-width → FAIL), ~90% → PASS,
    all outside → FAIL, threshold identifies hd days, below threshold no hd days,
    cold days counted, no cold days when mild, required keys present, verdict from
    allowed set.
- **No 2026 data downloaded or opened.** No real data files accessed.
- **Remaining work before run:** Dani must approve cs3_protocol.md (§2 status change).
  After approval: download 2026 data, run cs3_confirmation.py.
- **Files:** `energy_futures/experiments/cs3_confirmation.py` (new),
  `tests/test_cs3_confirmation.py` (new)
- **Test count:** 124 → 152 passed.

## Stage 12 · 25 Nov 2026 · cs3_protocol.md: three targeted corrections

- **Goal:** Fix three gaps in `docs/cs3_protocol.md` identified in review of commit e42aae1.
- **Changes:**
  - **§4 (Method):** Replaced "or a minimal wrapper" with explicit requirement:
    `energy_futures/experiments/cs3_confirmation.py` must be written, tested on synthetic
    data, and committed BEFORE any download. Existing 2026 guard in `load_development_data()`
    stays; the new wrapper adds an additional runtime date check.
  - **§8 (Co-primary 2):** Removed "Expected n ≈ 18–22 days (5% of ≈ Jan-Oct ≈ 304
    days)." Replaced with: threshold (44,411.96 MW) was set by 2023-2025 winter peaks,
    so actual n is likely smaller and concentrated in Jan–Feb.
  - **§11 (Prohibitions):** Added explicit carve-out: quarterly GBMQuantile refits
    ("QS", expanding window from 2009) using 2026 data available up to each refit date
    are PERMITTED as part of the frozen method. No other use of 2026 data permitted
    without approval.
- **Files:** `docs/cs3_protocol.md` (targeted edits only; status remains DRAFT)
- **No code or test changes.** No 2026 data downloaded.

## Stage 11 · 25 Nov 2026 · Fix H1–H3 definitions; relabel mean-cost gain as exploratory secondary

- **Goal:** Correct mislabelled H1–H3 definitions throughout docs. The previous
  statistical_tests.md used wrong definitions (H1=mean C<B; H2=p95 C<B;
  H3=mean C<none) and stated "H1 is statistically significant." The correct
  definitions (from configs/optimisation.yaml, D-035) are:
  - H1: "Setting H: C has lower p95 AND lower total shortfall than B, with mean ≤ B+1%."
  - H2: Decomposition — descriptive, not a significance test.
  - H3: "Setting F: C has lower p95 than B in at least 3 of 4 future cases."
- **H1 verdict:** Not statistically supported.
  - p95 component: CI [−596, +186] MW includes 0; p≈0.91.
  - Shortfall component: CI [−24.1, +0.2] GWh (7-day block bootstrap, n=663, seed=42)
    includes 0 (barely). Slight difference from Batch 6 value [−24.3, +0.3] GWh;
    same conclusion.
  - Mean sub-condition met: CI [−125, −25] MW excludes 0.
  - **H1 as a whole: NOT statistically supported.**
- **H3 verdict:** 3 of 4 future-case p95 point estimates favour C; all 4 CIs include 0.
  H3 met on point estimates only; not statistically supported.
- **Secondary exploratory finding (mean cost):** Historical 2024-25 mean-cost gain
  (p≈0.0072) survives Holm correction across m=5 mean-cost comparisons
  (threshold α/5=0.010). This is NOT H1; it is exploratory and secondary.
- **Files changed:**
  - `energy_futures/experiments/cs4_stats.py` — script restructured: added
    `run_shortfall_ci()`, `run_preregistered_h1_h3()`,
    `run_exploratory_mean_holm()`; removed wrong internal H1/H2 label mapping;
    added correct H1/H3 assessment from bootstrap CIs.
  - `docs/results/statistical_tests.md` — §3 fully rewritten: H1–H3 definitions
    corrected; "H1 is statistically significant" removed; added §3.3
    (pre-registered assessment), §3.4 (exploratory mean-cost Holm), updated §4
    summary, §5 change table.
  - `docs/results/optimisation_report.md` — table row "H1: mean cost ≤ B+1% | ...
    Met; significant" → "Mean cost sub-condition … exploratory secondary"; conclusion
    "significant on average cost" → "significant as exploratory secondary finding".
  - `docs/technical_report.md` — abstract line "statistically significant" →
    "significant as exploratory secondary finding"; table rows "Significant
    improvement" and "Significant" (C vs B+) → "Exploratory secondary: CI excludes 0"
    and "Exploratory: CI excludes 0".
  - `docs/ktp_case_study.md` — "significant on average cost" →
    "significant on average cost (exploratory secondary finding)".
  - `DECISIONS.md` D-038 — "mean-cost gain is significant" →
    "H1 is NOT statistically supported … mean-cost gain is significant as exploratory
    secondary finding".
- **Tests:** 124 passed (unchanged from Stage 9; test_cs4_stats.py still passes
  because all public function signatures are compatible).
- **Remaining uncertainty:** The exploratory mean-cost Holm uses approximate p-values
  from the normal approximation; the bootstrap CI is the primary evidence. The
  shortfall CI [−24.1, +0.2] GWh differs by ≤0.3 GWh from the Batch 6 value; the
  difference is due to block construction details and does not change the conclusion
  (CI includes 0 in both cases).

## Stage 10 · 25 Nov 2026 · CS-3 protocol rewrite

- **Goal:** Rewrite `docs/cs3_protocol.md` with precise, non-ambiguous specifications
  identified in review of commit be16f54.
- **Key changes:**
  - Status: "DRAFT – NOT approved by Dani" (was "DRAFT — committed before any 2026 data").
  - Removed "This document is Dani's written approval" — approval now requires explicit
    status change and commit by Dani.
  - Evaluation window fixed: 2026-01-01..2026-10-31 (was "determined at run time").
    If data missing, report available days; no extension.
  - Method fully specified: baseline exactly as at commit 304b7d8; GBMQuantile refit
    schedule "QS" (quarterly start), train from 2009-01-01; Mac machine (arm64 Darwin).
    Package versions recorded (Python 3.12.16, lightgbm 4.7.0, numpy 2.5.5, pandas 3.1.1).
  - High-demand threshold frozen: **44,411.96 MW** (95th percentile of daily-max raw q50
    over 2023-2025 eval window; computed from actual CS-2b data).
  - Pass criteria rewritten:
    - Co-primary 1: Coverage_90 on Jan-Feb 2026 ∈ [85%, 95%] (was 2026-Q1, [87%, 95%]).
    - Co-primary 2: Coverage_90 on high-demand days Jan-Oct ≥ 80% (point estimate);
      report 95% CI and n (was 2026-Q1 high-demand [75%, 100%]).
    - Secondary: overall Jan-Oct ∈ [88%, 92%] (expected range; not formal pass/fail).
    - Cold days: descriptive only.
  - Explicit PASS / FAIL / MIXED / INCONCLUSIVE reporting table added.
  - Exact download steps and sources for each 2026 data type, each with 2026-only guard.
  - Disclosure of 15,425 rows of NESO 2026 benchmark data already on disk (Batch 4,
    never used for modelling; two rows printed once). Added as §3.
  - Removed "dissertation".
- **No 2026 data downloaded or opened.**
- **Files:** `docs/cs3_protocol.md` (rewritten)

## Stage 9 · 25 Nov 2026 · CS-4 stats script + regenerated statistical tests report

- **Goal:** Make DM tests and Holm correction reproducible from a committed script;
  fix inaccuracies in statistical_tests.md identified in review of commit be16f54.
- **Script:** `energy_futures/experiments/cs4_stats.py` (new). Reads frozen
  `outputs/advanced/test/point_underlying_demand.parquet`,
  `outputs/advanced/test/point_nd.parquet`, and
  `outputs/optimisation/c_vs_b_bootstrap.csv` (read-only). Writes summary to
  `outputs/v2_cs4_stats/` (dm_tests.csv, holm_cvb.csv, summary.json).
- **Tests:** `tests/test_cs4_stats.py` (new, 14 tests):
  - Newey-West variance: lag=0 vs sample variance; iid convergence.
  - DM: identical forecasts → stat ≈ 0 or NaN; clearly better model → significant;
    clearly worse → positive and significant; MAE values correct.
  - Holm: hand-worked 3-test example; all-significant; none-significant; single test;
    order independence.
  - approx_pvalue_from_ci: CI excluding zero; CI including zero; known case.
- **Numbers that changed from previous doc** (script values used):
  - DM(FW vs naive, lag=1): −11.67 → −11.68 (−11.6788 rounded to 2dp)
  - DM(FW vs NESO, lag=1): +17.13 → +17.15 (+17.1536 rounded to 2dp)
  - Electric 2050 mean p-value: 0.032 → 0.033 (0.0325 rounded to 3dp)
  - Cost unit label: "£/MWh/day" → "MW (cost index)" (stylised index, not £)
  - Added lag=7 DM results: DM(FW vs naive) = −7.53; DM(FW vs NESO) = +15.15; both p < 0.001.
  - Pre-specified family corrected to H1-H3 (m=3); H3 not testable from saved outputs.
  - H1 Holm threshold corrected: 0.025 (m=2) → 0.0167 (m=3); H1 still survives (p=0.0072).
- **Removed:** "dissertation" references; speculation about why NESO is better; "£/MWh/day".
- **Added:** "approximate (normal approximation)" label on CI-derived p-values; §5 change log.
- **Test count:** 124 passed (14 new).
- **Files:**
  - `energy_futures/experiments/cs4_stats.py` (new)
  - `tests/test_cs4_stats.py` (new)
  - `docs/results/statistical_tests.md` (fully regenerated)
  - `outputs/v2_cs4_stats/` (new, gitignored)

## Stage 8 · 24 Nov 2026 · Corrections to conditional calibration report

- **Goal:** Fix three accuracy issues in `docs/results/conditional_calibration.md`
  identified in review of commit be16f54.
- **(a) §1 and §7:** Removed causal claim "primarily because the cold stratum falls back".
  Replaced with factual observations: Mondrian fell back on 26/47 cold days (55%);
  Mondrian extended had 0% cold fallback yet lower cold coverage (85.5% vs 86.3%).
  Causes not established from these data.
- **(b) §9 Limitation #7 added:** Pre-registration design flaw — the high-demand
  stratum is defined as the top 5% of daily-max q50 within the 365-day window, yielding
  at most 18 high-demand days per window (5% × 365 = 18.25), which is below the
  MIN_DAYS_STRATUM = 20 fallback threshold. Candidates A and C structurally could never
  accumulate enough high-demand calibration days; they fell back to global for 100% of
  high-demand evaluation days. Identified post-results; cannot be corrected within this
  pre-registration.
- **(c) §4.1 and §1:** Added explicit statement that all candidate-vs-baseline differences
  in cold and high-demand Coverage_90 fall within overlapping 95% bootstrap CIs
  (n = 47 cold days, n = 42 high-demand days); no difference is distinguishable from noise.
- **Files changed:** `docs/results/conditional_calibration.md` (§1, §4.1, §7, §9)
- **No code, data or results changed.**

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
