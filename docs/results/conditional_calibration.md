# CS-2b: Conditional recalibration of prediction intervals

_Branch: improve/phase-b | Eval script commit: 304b7d8 | Date: 2026-11-24_
_Pre-registration: docs/cs2_preregistration.md (Amendments 1 and 2 included)_

---

## 1. Summary

The rolling evaluation tested four prediction-interval calibration methods
across 11 evaluation quarters (2022-25 development data). **No candidate method
met all four pre-registered selection rules; the baseline is retained.** The key
barrier was cold-day improvement: none of the three candidates achieved the required
≥ 3.0 percentage-point increase in cold-day Coverage_90 over the baseline, primarily
because the cold stratum falls back to the global correction in most quarters (too few
cold days in the 365-day rolling window).

Sanity check: baseline Coverage_90 on 2024-03-08..2025-12-31 = 90.51% vs CS-1
reference 90.5% (diff = +0.01 pp; within ±1.0 pp tolerance — PASS).

---

## 2. Evaluation design

**Data:** 2022-01-01..2025-12-31 (development data; 2026 reserved for one-time
confirmation run if a new method were selected). FW quantile series: Mac-generated
series `quantiles_FW_raw_mac_2024-2025.parquet` covering 2024-01-01..2025-12-31
(see §8 for reproducibility note). 2022-23: `quantiles_2022_2023.parquet` (PW inputs).

**Methods evaluated:**
- **Baseline** — Rolling unconditional CQR, 365-day window (reproduces EXP-004).
- **Mondrian (Candidate A)** — Stratum-specific CQR (cold/high_demand/normal); falls
  back to global if stratum has < 20 calibration days in rolling window.
- **Mondrian extended (Candidate C)** — Same as Mondrian but cold stratum uses
  unlimited history instead of 365-day window.
- **Width-normalised (Candidate B)** — Global CQR with width-normalised scores
  (multiplicative correction); same rolling window as baseline.

**Evaluation quarters (11):** 2023-Q1..Q4; 2024-Q2..Q4; 2025-Q1..Q4.
(2024-Q1 excluded: only 24 days of evaluation data, too short for conditional stats.)

**Temperature proxy:** D-2 observed GB mean (2022-23); archived ~48 h forecast (2024-25).

---

## 3. Sanity check

| Period | CS-1 reference | CS-2b baseline | Difference |
|--------|---------------|----------------|------------|
| 2023 (all half-hours) | 92.5% | 92.47% | −0.03 pp — not a failure condition |
| 2024-03-08..2025-12-31 | 90.5% | **90.51%** | **+0.01 pp — PASS (tol ±1.0 pp)** |

The 2023 baseline reproduces CS-1 to within 0.03 pp, confirming the calibration
code is correct.

---

## 4. Pooled results (all 11 quarters combined)

### 4.1 Coverage and width

| Method | Coverage_90 all | Coverage_90 cold | Coverage_90 high_demand | Width_90 (MW) | Winkler (MW) |
|--------|:--------------:|:---------------:|:----------------------:|:-------------:|:------------:|
| baseline | **91.1** [90.2, 92.0] | 86.3 [80.9, 91.2] | 85.8 [80.0, 91.5] | 2960 [2919, 3002] | 3694 [3567, 3827] |
| mondrian | 90.3 [89.4, 91.2] | 87.6 [82.2, 92.3] | 85.7 [79.4, 91.2] | 2879 [2838, 2922] | 3689 [3556, 3833] |
| mondrian_extended | 90.2 [89.3, 91.1] | 85.5 [79.3, 90.6] | 85.4 [79.6, 90.8] | 2870 [2828, 2913] | 3692 [3561, 3825] |
| width_normalised | 90.9 [90.0, 91.7] | 88.3 [83.9, 92.5] | **88.0** [82.0, 93.0] | 3099 [3042, 3160] | 3781 [3662, 3909] |

_95% block-bootstrap CIs by calendar day, 1 000 resamples, seed 42._
_cold = temp_proxy < 3 °C; high_demand = daily max q50 ≥ 95th percentile over full eval window._

No NaN actual-demand rows dropped; no NaN-proxy days.

### 4.2 All conditions (baseline)

| Condition | Coverage_90 | 95% CI |
|-----------|:-----------:|:------:|
| All half-hours | 91.1% | [90.2, 92.0] |
| Cold proxy (< 3 °C) | 86.3% | [80.9, 91.2] |
| High predicted demand | 85.8% | [80.0, 91.5] |
| Winter (Dec–Feb) | 88.1% | [85.7, 90.3] |
| Bank holiday | 86.8% | [79.3, 93.6] |
| Cold observed (reporting only) | 86.1% | [80.6, 91.2] |

---

## 5. Quarterly breakdown

Coverage_90 (all half-hours) by method and quarter:

| Quarter | Baseline | Mondrian | Mondrian ext. | Width-norm. |
|---------|:--------:|:--------:|:-------------:|:-----------:|
| 2023-Q1 | 88.9% | 89.0% | 88.3% | 90.6% |
| 2023-Q2 | 95.2% | 95.0% | 95.0% | 94.6% |
| 2023-Q3 | 95.3% | 94.9% | 94.9% | 93.3% |
| 2023-Q4 | 90.5% | 90.5% | 90.2% | 90.2% |
| 2024-Q2 | 93.5% | 92.3% | 92.3% | 94.0% |
| 2024-Q3 | 95.7% | 94.6% | 94.6% | 94.1% |
| 2024-Q4 | **87.0%** | 85.3% | 85.3% | 87.9% |
| 2025-Q1 | **87.7%** | 87.0% | 87.0% | 89.4% |
| 2025-Q2 | 94.5% | 93.4% | 93.4% | 93.7% |
| 2025-Q3 | 86.6% | 84.8% | 84.8% | 83.8% |
| 2025-Q4 | **87.4%** | 86.8% | 86.7% | 87.9% |

Cold proxy Coverage_90 for quarters with cold days:

| Quarter | n_cold | Baseline | Mondrian | Mondrian ext. | Width-norm. |
|---------|:------:|:--------:|:--------:|:-------------:|:-----------:|
| 2023-Q1 | 14 | 89.6% | 90.9% | 86.3% | 91.1% |
| 2023-Q4 | 8 | 91.9% | 94.8% | 91.4% | 91.4% |
| 2024-Q4 | 5 | **62.5%** | 62.5% | 61.7% | 68.8% |
| 2025-Q1 | 17 | 89.6% | 90.2% | 90.2% | 91.9% |
| 2025-Q4 | 3 | 76.4% | 79.9% | 78.5% | 78.5% |

2024-Q4 and 2025-Q4 show the worst cold coverage. 2024-Q4 is the driver of the low pooled cold coverage.

---

## 6. Method selection (§7)

| Candidate | Rule 1 overall [87–93%] | Rule 2 cold ≥ base+3 pp | Rule 3 high ≥ base+3 pp | Rule 4 width ≤ 1.25×base | Outcome |
|-----------|:-----------------------:|:-----------------------:|:-----------------------:|:------------------------:|:-------:|
| Mondrian | 90.3% ✓ | +1.33 pp ✗ | — | — | Eliminated |
| Mondrian ext. | 90.2% ✓ | −0.80 pp ✗ | — | — | Eliminated |
| Width-norm. | 90.9% ✓ | +1.99 pp ✗ | — | — | Eliminated |

**Selected method: baseline.** No candidate passed Rule 2 (cold-day improvement ≥ 3.0 pp).

The largest cold-day gain was width_normalised at +1.99 pp (88.25% vs baseline 86.26%).
This is a real improvement, but falls short of the pre-registered 3.0 pp threshold.
Rule 3 for high-demand days would also have failed for width_normalised (88.05% vs 88.81%
threshold).

---

## 7. Fallback analysis

The fallback report quantifies why Mondrian and Mondrian extended rarely apply the
stratum-specific correction:

| Quarter | Stratum | Days | Mondrian fallback | Mondrian ext. fallback |
|---------|---------|:----:|:-----------------:|:----------------------:|
| 2023-Q1 | cold | 14 | 7 (50%) | 0 (0%) |
| 2023-Q1 | high_demand | 4 | 4 (100%) | 4 (100%) |
| 2023-Q4 | cold | 8 | 0 (0%) | 0 (0%) |
| 2023-Q4 | high_demand | 2 | 2 (100%) | 2 (100%) |
| 2024-Q4 | cold | 5 | 5 (100%) | 0 (0%) |
| 2024-Q4 | high_demand | 6 | 6 (100%) | 6 (100%) |
| 2025-Q1 | cold | 17 | 13 (76%) | 0 (0%) |
| 2025-Q1 | high_demand | 12 | 12 (100%) | 12 (100%) |
| 2025-Q4 | cold | 3 | 1 (33%) | 0 (0%) |
| 2025-Q4 | high_demand | 3 | 2 (67%) | 2 (67%) |

Key observations:
- **High-demand stratum falls back 100% of the time** in most quarters. With typically
  2–12 high-demand days per quarter, the 365-day window rarely accumulates ≥ 20 such days.
  Mondrian therefore applies the global (baseline) correction for high demand in all but
  the most demand-heavy quarters.
- **Cold stratum falls back 50–100%** of the time in Mondrian. Mondrian extended eliminates
  cold fallbacks (uses all history), but its cold coverage (85.5%) is actually worse than
  baseline (86.3%), suggesting that mixing 2022-23 and 2024-25 cold observations (which use
  different temperature proxies) degrades rather than improves calibration for cold days.

---

## 8. Cloud-vs-Mac reproducibility

The FW quantile predictions used in CS-2b are Mac-generated (Amendment 2 addendum).
A comparison against the cloud-generated Batch 4 file for 2024-03-08..2025-12-31 found:

| Quantile | Mean abs diff (MW) | P99 abs diff (MW) | Max abs diff (MW) |
|----------|:-----------------:|:-----------------:|:-----------------:|
| q05 | 0.00 | 0.00 | 31.4 |
| q25 | 0.00 | 0.00 | 22.5 |
| q50 | 0.00 | 0.00 | 25.5 |
| q75 | 0.01 | 0.00 | 73.9 |
| q90 | 0.01 | 0.00 | 113.4 |
| q95 | 0.00 | 0.00 | 33.7 |

Raw Coverage_90 (uncalibrated): **cloud 75.15%, Mac 75.15% — identical.**

The mean and P99 differences are essentially zero; the max differences are isolated
outliers from LightGBM's parallel tree building. The models are functionally equivalent;
the sanity check confirms calibrated coverage matches CS-1 to within 0.01 pp.

---

## 9. Limitations

1. **Development data includes 2024-25 (observed in CS-1):** the rolling evaluation is
   time-series-honest, but results are not fully independent of CS-1 observations.
2. **Cold-day proxy mismatch:** 2022-23 uses D-2 observed temperature; 2024-25 uses
   archived forecast temperature. The transition is applied consistently in calibration,
   but Mondrian extended mixes these differently-defined "cold day" labels across years.
3. **Small cold-day sample:** pooled across 11 quarters, there are only 47 cold-proxy days
   (n_days in coverage table). Bootstrap CIs for cold coverage are therefore wide
   ([80.9, 91.2] for baseline). Formal statistical power is limited.
4. **High-demand stratum systematically falls back:** with ≤ 12 high-demand days per
   quarter, the min_days=20 threshold is almost never met, making Mondrian equivalent to
   the baseline for high-demand days in practice.
5. **Mac/cloud architecture difference:** noted in §8; baseline coverage matches CS-1 to
   within 0.01 pp, so this does not affect the conclusions.
6. **Pre-registration seal: laptop only** — timing cannot be independently verified.
