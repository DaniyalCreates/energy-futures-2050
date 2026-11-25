# CS-3 Confirmation Run — 2026

_Run date: 2026-11-25 | Branch: improve/phase-b | Protocol: docs/cs3_protocol.md_
_Commit: see git log on improve/phase-b (Stage 20)_

---

## Summary

The baseline rolling unconditional CQR — the method selected by CS-2b — was applied
to genuinely unseen 2026 data (2026-01-01 to 2026-10-31, 304 days, 14,592 half-hours)
as a pre-registered consistency check. The question was: does the interval calibrated on
2022–25 data continue to achieve approximately its historical coverage rate when facing
2026 conditions?

**Verdict: PASS.**

Both pre-registered co-primary criteria are met. The 90% prediction interval covered
actual demand in 89.8% of Jan–Feb half-hours (pre-registered target 85–95%) and in
90.9% of half-hours on the 17 highest-demand days Jan–Oct (pre-registered minimum 80%;
95% bootstrap CI 82.8–95.8% using 7-day block bootstrap, entirely above the 80%
threshold). The Jan–Oct overall coverage of 89.4% falls within the expected 88–92% range.

PASS means the calibration holds overall and on the highest-demand days. It does not mean
all conditions are equally well covered. Cold days (temperature < 3 °C, n=11) show 84.7%
coverage — below the 85–95% band and consistent with the known weakness identified in
EXP-004. This is a descriptive observation; cold-day performance was not a pass/fail
criterion in the protocol.

This supports the conclusion that the baseline calibration is not over-fitted to
2022–25 patterns.

---

## Verdict (verbatim from cs3_verdict.txt)

> CS-3 VERDICT: PASS
>
> Co-primary 1 (Jan-Feb Coverage_90): 89.8% [85–95%] → PASS. Co-primary 2
> (high-demand Coverage_90, n=17): 90.9% [≥80%] → PASS. Secondary (Jan-Oct
> Coverage_90): 89.4% [88–92% expected]. Cold days (descriptive, n=11): 84.7%.

---

## Criteria in detail

| Criterion | Period | Coverage_90 | n days | 95% CI | Threshold | Outcome |
|-----------|--------|:-----------:|:------:|:------:|-----------|---------|
| Co-primary 1 | Jan–Feb 2026 | **89.8%** | 59 | — | [85%, 95%] | **PASS** |
| Co-primary 2 | Jan–Oct 2026, high-demand | **90.9%** | 17 | [82.8%, 95.8%] | ≥ 80% | **PASS** |
| Secondary (expected range, not pass/fail) | Jan–Oct 2026, overall | 89.4% | 304 | — | [88%, 92%] expected | Within range |
| Cold days (descriptive) | Jan–Oct 2026, temp < 3 °C | 84.7% | 11 | — | — | Descriptive |

**Coverage_90** = fraction of half-hours where actual underlying demand ∈ [q05, q95]
of the calibrated interval, expressed as a percentage.

**High-demand threshold:** 44,411.96 MW (95th percentile of daily-max raw q50 over
2023–2025, frozen at CS-2b §6; selection used raw q50 from GBMQuantile, not calibrated
q50, per protocol §6).

**95% CI for co-primary 2:** moving block bootstrap resampling days (not individual
half-hours) in contiguous 7-day blocks, n_boot=1,000, seed=42. Each resampled day
contributes all 48 half-hours. All 1,000 bootstrap samples yielded coverage ≥ 80%.

The high-demand threshold was set by winter peaks, so n=17 is smaller than 5% × 304
would suggest; days are concentrated in January–February as expected (§8 of protocol).

---

## Disclosures

1. **Batch 4 2026 rows.** The NESO day-ahead benchmark file already on disk contained
   2026 rows. They were loaded in Batch 4 but never used for modelling; two rows (18 Nov
   2026) were printed once while checking the file format. This is documented in the
   research changelog ground rules.

2. **Mac-only run.** The GBMQuantile refits and CQR calibration were run on Dani's Mac
   (arm64, macOS 15.7.7, Apple Silicon). This project's own measurement (CS-2 Amendment
   2, `docs/cs2_preregistration.md` §12): cloud vs Mac quantile differences — mean
   absolute diff ≈ 0.0 MW across all quantile levels; maximum isolated difference 113 MW
   (architecture-dependent LightGBM parallelism, same code, config and seed); raw
   Coverage_90 over 2024-03-08..2025-12-31 is identical cloud vs Mac (75.15%). The 2026
   quantile file (`quantiles_FW_raw_mac_2026.parquet`) is therefore arm64-generated; an
   x86 re-run would likely differ by rounding, but Coverage_90 is insensitive to
   rounding-level quantile changes.

3. **Timing.** The NESO and ERA5 2026 raw files were downloaded and the confirmation run
   completed on 2026-11-25. No 2026 demand values or statistics were inspected before
   the run completed (the schema-guard error that triggered Deviation 1 printed column
   names only, not values).

4. **Deviation 1.** A processing bug (Stage 14 code dropped per-city weather columns,
   22 of 46) was caught by the Stage 17 schema guard before any 2026 quantile,
   calibration or coverage was computed. The fix was approved by Dani and recorded in
   docs/cs3_protocol.md § Deviations.

---

## Package versions and runtime

| Package   | Version                                     |
|-----------|---------------------------------------------|
| Python    | 3.12.16 (Clang 23.1.3, arm64)               |
| lightgbm  | 4.7.0                                       |
| numpy     | 2.5.5                                       |
| pandas    | 3.1.1                                       |
| platform  | macOS-15.7.7-arm64-arm-64bit                |

**Runtime:** `generate_cs3_quantiles.run()` 201 s (4 QS refits, start_pw 2009-01-01);
`cs3_confirmation.run()` 2 s.

Refit log:

| Block start | Train end | n eval rows |
|-------------|-----------|:-----------:|
| 2026-01-01  | 2025-12-31 | 4,318 |
| 2026-04-01  | 2026-03-31 | 4,368 |
| 2026-07-01  | 2026-06-30 | 4,416 |
| 2026-10-01  | 2026-09-30 | 1,490 |

---

## Output files

| File | Contents |
|------|----------|
| `outputs/v3_cs3_confirmation/cs3_verdict.txt` | Verdict and full metrics (machine-readable) |
| `outputs/v3_cs3_confirmation/metrics_by_period.csv` | Per-period coverage and bootstrap CIs |
| `outputs/v3_cs3_confirmation/package_versions.txt` | Environment record |
| `outputs/v3_cs3_confirmation/inputs/quantiles_FW_raw_mac_2026.parquet` | Raw GBMQuantile 2026 predictions (14,592 rows, q05–q95) |
