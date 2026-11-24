# CS-3 Protocol — confirmation run on 2026 data

_Status: DRAFT — committed before any 2026 data is downloaded or opened._
_Branch: improve/phase-b | Date: 2026-11-24_
_Parent pre-registration: docs/cs2_preregistration.md §8.5_

---

## 1. Motivation and status

CS-2b selected the **baseline** (rolling unconditional CQR) as the method to carry
forward: no candidate met the pre-registered improvement threshold for cold-day
Coverage_90. The confirmation run therefore applies the same baseline method to
2026 data as a consistency check: does the baseline continue to deliver approximately
its historical coverage rate when facing truly unseen data?

This run is **not** a test of a new method. Its purpose is to verify that the baseline
calibration is not over-fitted to 2022-25 and that Coverage_90 on 2026 data is
consistent with CS-1 and CS-2b findings.

---

## 2. This document must be committed before any 2026 data is accessed

Per CLAUDE.md and the pre-registration §10:
> Do not access, download, or open 2026 data before the confirmation run is approved.

This document is Dani's written approval of the CS-3 protocol. No 2026 data should be
downloaded, opened, or used until this document is committed to `improve/phase-b`.

---

## 3. Method

**Method:** Baseline rolling unconditional CQR (identical to CS-2b baseline; no changes).

**Script:** `energy_futures/experiments/cs2_rolling_eval.py` or a minimal wrapper that
calls `load_development_data()` with 2026 data added, then `evaluate()` restricted to
the 2026 evaluation window.

**Quantile model:** The existing Mac-generated model (via `quantiles_FW_raw_mac_2024-2025.parquet`
for the calibration history). For 2026 predictions, the GBMQuantile model must be
re-run on 2026 demand and forecast weather data to produce `quantiles_FW_raw_mac_2026.parquet`
(new file, same quarterly-refit GBMQuantile config).

**Calibration window:** Rolling 365-day window, identical to CS-2b baseline.

---

## 4. Evaluation period

**Start:** 2026-01-01  
**End:** Determined by data availability at run time (expected 2026-01 to 2026-10 or later).

**Evaluation quarters (provisional — fixed at run time):**
- 2026-Q1 (Jan–Mar 2026): co-primary metric
- 2026-Q2 (Apr–Jun 2026): secondary if available
- 2026-Q3 (Jul–Sep 2026): secondary if available
- 2026-Q4 (Oct–Dec 2026): secondary if available; may be partial

2026-Q1 is the only quarter guaranteed to contain winter months (Jan-Feb), making it
the most informative for cold-day consistency.

---

## 5. Pre-declared pass criteria

**Primary metric 1 — Overall Coverage_90 on 2026-Q1:**

> PASS if 2026-Q1 overall Coverage_90 ∈ [87%, 95%].

This is a wider interval than the CS-2b selection guard of [87%, 93%], to allow for
small-sample variability in a single quarter (≈90 days, ≈4 320 half-hours).
A result below 87% suggests the baseline is degrading. A result above 95% suggests
the intervals are over-wide. Either would warrant investigation before publication.

**Primary metric 2 — High-demand Coverage_90 on 2026-Q1:**

> PASS if 2026-Q1 high-demand Coverage_90 ∈ [75%, 100%].

The wide lower bound (75%) reflects the small high-demand sample per quarter (typically
5–15 days). The 2024-Q4 cold under-coverage (62.5%) observed in CS-2b is an existence
proof that short periods can be highly variable; the CS-3 criterion is set generously
to detect only severe degradation.

**Reporting-only metrics (not formal pass/fail):**
- Cold-proxy Coverage_90 on 2026-Q1 (expected too few cold days for formal inference)
- Coverage_90 for all available 2026 quarters (Q2-Q4 if present)
- Coverage_80, Coverage_50 for 2026-Q1

**Failure action:** If either primary metric fails:
1. Report the finding verbatim.
2. Do not publish as a successful validation.
3. Investigate whether failure is due to data quality, a distributional shift, or a
   code error.
4. Seek Dani's guidance before any further action.

---

## 6. Data requirements

| Data needed | Source | Guard |
|-------------|--------|-------|
| Actual underlying demand, 2026 | NESO (via pipeline) | Only for 2026-01-01 onward |
| Observed temperature, 2026 | demand_weather pipeline | Only for 2026-01-01 onward |
| Forecast temperature, 2026 | Open-Meteo archived forecasts | Only for 2026-01-01 onward |
| Forecast radiation, 2026 | Open-Meteo archived forecasts | Only for 2026-01-01 onward |

**2026 data is reserved for ONE run.** Once any 2026 data has been loaded for this
run, no changes to the method, thresholds, or reporting criteria are permitted.

---

## 7. Prohibitions (from pre-registration §10, repeated here)

- Do not change the calibration method, window, or thresholds before or after seeing
  2026 results.
- Do not modify the pass criteria in §5 after any 2026 data has been accessed.
- Do not use 2026 data for any other purpose (e.g., model retraining, feature selection,
  additional experiments) without Dani's explicit approval.
- Do not modify `outputs_archive/v1_5db4552/`.

---

## 8. Outputs

All results to `outputs/v3_cs3_confirmation/` (new versioned folder, never overwrites CS-2b).

Required files:
- `metrics_by_quarter.csv` (CS-3 quarters only)
- `metrics_pooled.csv` (over all 2026 evaluation data)
- `sanity_check.txt` (baseline 2026-Q1 vs pass criteria §5)
- `cs3_verdict.txt` (PASS / FAIL with values and reasons)

---

## 9. Relationship to publication

The CS-3 confirmation run result — PASS or FAIL — will be reported verbatim in the
technical report (§7 of `docs/technical_report.md`). No result will be suppressed or
retrospectively re-labelled.

If the baseline PASSES: the dissertation and KTP case study may state that the existing
calibration is validated on 2026 data.

If the baseline FAILS: the write-up will note the failure and its implication (the
baseline may be over-fitted to 2022-25 patterns; the intervals may need refinement).
