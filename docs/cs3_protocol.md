# CS-3 Protocol — confirmation run on 2026 data

_Status: **DRAFT – NOT approved by Dani**_
_Branch: improve/phase-b | Date: 2026-11-25_
_Parent pre-registration: docs/cs2_preregistration.md §8.5_

---

## 1. Purpose

CS-2b selected the **baseline** (rolling unconditional CQR) as the method to carry
forward: no candidate met the pre-registered improvement threshold for cold-day
Coverage_90. The confirmation run applies the same baseline method to truly unseen
2026 data as a consistency check: does the baseline continue to deliver approximately
its historical coverage rate when facing 2026 conditions?

This run is **not** a test of a new method. Its purpose is to verify that the baseline
calibration is not over-fitted to 2022-25.

---

## 2. Approval gate

**This document must be approved and committed BEFORE any 2026 data is downloaded
or opened.**

This document is a DRAFT. It is NOT yet approved by Dani. No 2026 data should be
downloaded, opened, or loaded into any script until Dani explicitly approves by
changing the status line above to "APPROVED by Dani — [date]" and committing that
change to `improve/phase-b`.

---

## 3. Disclosure: 2026 data already on disk (Batch 4)

As noted in the ground rules of `docs/research_changelog.md`:

> The NESO day-ahead benchmark file already on disk contains 2026 rows.
> They were loaded in Batch 4 but never used for modelling; two rows (18 Nov 2026)
> were printed once while checking the file format. The 15,425 rows of 2026 NESO
> benchmark data remain on disk untouched.

This disclosure applies only to the NESO benchmark ND forecast file. No 2026 actual
demand, observed temperature, or forecast weather data has been accessed for modelling
purposes. The CS-3 approval gate in §2 refers to these unaccessed data sources.

---

## 4. Method

**Method:** Baseline rolling unconditional CQR — identical to the method frozen at
commit 304b7d8 on branch `improve/phase-b`. No changes to method code; the wrapper
and data scripts listed here must be committed before approval.

**Calibration window:** Rolling 365-day window, identical to CS-2b baseline.

**CQR interval:** 90% (α = 0.10), consistent with CS-1 and CS-2b.

**Script:** `energy_futures/experiments/cs2_rolling_eval.py` — method functions are
unchanged. A separate loader/wrapper, `energy_futures/experiments/cs3_confirmation.py`,
is used to load 2026 data from the protocol paths, enforce the date guard
(2026-01-01..2026-10-31), and write `cs3_verdict.txt`. This wrapper:

- **Must be written, tested on synthetic data, and committed BEFORE any 2026 data is
  downloaded.** Dani must approve this document (§2) before the download.
- Uses only the method code already frozen at commit 304b7d8; no new parameters or
  model logic.
- The existing 2026 guard in `load_development_data()` stays in place; `cs3_confirmation.py`
  adds an additional runtime check that no dates outside 2026-01-01..2026-10-31 are
  evaluated.

---

## 5. Quantile model

**Model:** GBMQuantile (LightGBM quantile regression), 7 quantile levels
(τ = 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95), forecast-weather inputs (FW).

**Hyperparameters:** As in EXP-004 (`configs/advanced.yaml`):
- `random_state = 42`
- `n_jobs = -1`
- `n_estimators = 600`
- Train start: 2009-01-01

**Refit schedule:** Quarterly start (`"QS"`) — model refitted at the start of each
calendar quarter, as in EXP-004 and the Mac regeneration run (commit 304b7d8).

**Machine:** Dani's Mac (arm64 Darwin). The same machine that produced
`quantiles_FW_raw_mac_2024-2025.parquet`. LightGBM parallelism is architecture-dependent
(see Amendment 2 addendum in cs2_preregistration.md §12); using the same machine
ensures internal consistency.

**Package versions at time of protocol draft:**
- Python: 3.12.16
- lightgbm: 4.7.0
- numpy: 2.5.5
- pandas: 3.1.1
- platform: arm64 Darwin

Package versions must be recorded again at the time of the actual run and compared
to these. Any version change must be noted in the changelog.

**New output file:** `outputs/v3_cs3_confirmation/inputs/quantiles_FW_raw_mac_2026.parquet`
(2026-01-01..2026-10-31; never overwrites CS-2b files).

---

## 6. High-demand threshold (frozen)

The high-demand threshold used for CS-3 is frozen at the CS-2 value:

> **Threshold: 44,411.96 MW**

This is the 95th percentile of daily-maximum raw q50 over the full CS-2b evaluation
window (2023-01-01..2025-12-31), computed from `quantiles_FW_raw_mac_2024-2025.parquet`
and `quantiles_2022_2023.parquet`. It was used throughout CS-2b and must be carried
forward unchanged.

A day qualifies as high-demand in CS-3 if its daily-maximum q50 ≥ 44,411.96 MW
(where q50 is from the CS-3 GBMQuantile forecast for that day).

---

## 7. Evaluation period

**Start:** 2026-01-01  
**End:** 2026-10-31 (fixed)

If data are unavailable for the full window, the run proceeds with the available
dates, the number of available days is reported, and no extension of the window is
permitted. The pass criteria in §8 are assessed on whatever half-hours are available
within 2026-01-01..2026-10-31.

---

## 8. Pre-declared pass criteria

These criteria are fixed by this document and may not be changed after any 2026 data
is loaded.

### Co-primary criterion 1 — Coverage_90, Jan-Feb 2026

> **PASS if Coverage_90 on 2026-01-01..2026-02-28 half-hours ∈ [85%, 95%].**

Motivation: January-February is the highest-risk period for the interval (most cold,
high-demand, and volatile conditions). The window is ≈ 59 days (≈ 2 832 half-hours).
The bounds [85%, 95%] are wider than the CS-2b overall bounds [87%, 93%] to allow
for single-period variability. A result below 85% suggests interval degradation.
A result above 95% suggests over-width.

### Co-primary criterion 2 — Coverage_90, high-demand days, Jan-Oct 2026

> **PASS if point estimate of Coverage_90 on high-demand days (2026-01-01..2026-10-31)
≥ 80%. Report the 95% bootstrap CI and n (number of high-demand days).**

High-demand day definition: daily-maximum q50 ≥ 44,411.96 MW (threshold frozen in §6).
The 44,411.96 MW threshold was set by 2023-2025 winter peaks, so the actual n of
high-demand days in 2026 is likely smaller than 5% × 304 days would suggest, and
concentrated in January-February when demand is highest. No lower bound is set for n;
if n < 5 the CI is too wide for inference and the result is reported as descriptive only.

### Secondary — overall Coverage_90, Jan-Oct 2026

> **Expected range [88%, 92%]** — not a formal pass/fail criterion; reported for
> consistency with CS-1 and CS-2b overall results.

### Cold days — descriptive only

Cold-day Coverage_90 (temp_proxy < 3 °C, archived forecast for 2026) is reported
but not subject to any pass/fail criterion. Expected n is small (< 20 days).

---

## 9. Reporting: PASS, FAIL, mixed

| Scenario | Label | Action |
|----------|-------|--------|
| Both co-primaries PASS | PASS | Report as confirmation of baseline validity |
| Either co-primary FAILS | FAIL | Report verbatim; investigate before publication |
| Co-primary 2 has n < 5 high-demand days | INCONCLUSIVE (high-demand) | Report co-primary 1 verdict only; note data insufficiency |
| Co-primary 1 PASS, co-primary 2 FAIL | MIXED | Report both results; note inconsistency |

**Failure action:** If either primary metric fails (or is MIXED):
1. Report the finding verbatim.
2. Do not report as a successful validation.
3. Investigate whether failure is due to data quality, distributional shift, or a code error.
4. Seek Dani's guidance before any further step.

**No result will be suppressed or retrospectively re-labelled.**

---

## 10. Data download steps

Each download is guarded to 2026-01-01..2026-10-31 only.

| Data | Source | Download command / path | 2026 guard |
|------|--------|------------------------|------------|
| Actual underlying demand | NESO API (same pipeline as `data/processed/demand_weather.parquet`) | Existing pipeline; append 2026 rows; save to `data/processed/demand_weather_2026.parquet` | Restrict to 2026-01-01 onward |
| Observed temperature (GB mean) | Same demand_weather pipeline (ERA5 / Open-Meteo historical) | Append to same 2026 file | Restrict to 2026-01-01 onward |
| Archived forecast temperature, 2026 | Open-Meteo API (same endpoint as 2024-25 JSON files in `data/raw/weather_forecast/`) | Per-city JSON files `{city}_2026.json`; same 6 cities as EXP-004 | Only request 2026-01-01..2026-10-31 |
| Archived forecast radiation, 2026 | Open-Meteo API (same endpoint) | Included in city JSON files above | Only request 2026-01-01..2026-10-31 |

**None of these downloads should be run until Dani approves this protocol (§2).**

**2026 data is reserved for ONE run.** Once any 2026 actual demand or weather data has
been loaded for model running or evaluation, no changes to the method, thresholds, or
pass criteria are permitted.

---

## 11. Prohibitions

- Do not change the calibration method, window, thresholds, or pass criteria before
  or after seeing 2026 results.
- Do not modify the pass criteria in §8 after any 2026 data has been accessed.
- **Permitted use of 2026 data:** Quarterly GBMQuantile refits ("QS", expanding window
  from 2009-01-01) using 2026 data available up to each refit date are **part of the
  frozen method** (§5). This is the only permitted use of 2026 data beyond evaluation.
- Do not use 2026 data for any other purpose (feature selection, threshold changes,
  additional experiments, calibration window changes) without Dani's explicit approval.
- Do not modify `outputs_archive/v1_5db4552/` or any CS-2b outputs.
- Do not access 2026 data before Dani approves this protocol (§2).

---

## 12. Outputs

All results to `outputs/v3_cs3_confirmation/` (new versioned folder).

Required files:
- `inputs/quantiles_FW_raw_mac_2026.parquet` (raw GBMQuantile FW predictions, 2026)
- `metrics_by_period.csv` (Jan-Feb and Jan-Oct breakdowns, plus cold days)
- `cs3_verdict.txt` (PASS / FAIL / MIXED / INCONCLUSIVE with values, criteria, and reasons)
- `package_versions.txt` (Python, lightgbm, numpy, pandas, platform at run time)

---

## 13. Relationship to write-up

The CS-3 confirmation run result — PASS, FAIL, MIXED, or INCONCLUSIVE — will be
reported verbatim in `docs/technical_report.md` (§7). No result will be suppressed or
retrospectively re-labelled.

If the baseline PASSES: the write-up may state that the baseline calibration is
validated on 2026 data.

If the baseline FAILS or is MIXED: the write-up will note the failure and its
implication (the baseline may be over-fitted to 2022-25 patterns; the intervals may
need refinement).
