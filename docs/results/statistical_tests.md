# CS-4: Statistical significance tests on frozen results

_Branch: improve/phase-b | Script: energy_futures/experiments/cs4_stats.py | Date: 2026-11-25_
_All inputs from: outputs/advanced/test/ and outputs/optimisation/ (frozen after Batch 8)._
_No 2026 data accessed. No models retrained._
_All numbers in §§2–3 are reproduced by running cs4_stats.py on the frozen files._

---

## 1. Purpose

This document applies formal significance tests to two sets of existing results:
1. **Point forecast accuracy** (Batch 4 / EXP-004): Diebold-Mariano tests comparing
   LightGBM FW vs naive_d7 (underlying demand) and LightGBM FW vs NESO (ND).
2. **Battery optimisation arm comparisons** (Batch 6 / EXP-006): Holm-corrected
   p-values derived from the existing block-bootstrap CIs (C vs B, all settings).

These tests are **exploratory** (not pre-registered for Batch 4 or 6): they provide
formal inference to complement the previously reported CIs, but do not change any
published finding.

---

## 2. Diebold-Mariano tests (point forecast accuracy)

**Method:** Diebold-Mariano (1995) test with Newey-West HAC variance (Bartlett kernel).
Losses aggregated to daily mean absolute error (MAE) before the test, to reduce
within-day autocorrelation. Evaluation window: 2024-03-08..2025-12-31
(fw_comparison_start, n = 664 calendar days). Two-sided tests, reported at lags 1 and 7.

**Script inputs:** `outputs/advanced/test/point_underlying_demand.parquet`,
`outputs/advanced/test/point_nd.parquet` (read-only).

### 2.1 LightGBM FW vs naive_d7 — underlying demand

| Model | Daily MAE (MW) |
|-------|:--------------:|
| LightGBM FW | 664 |
| naive_d7 | 1 281 |

| Statistic | Lag = 1 | Lag = 7 |
|-----------|--------:|--------:|
| Mean loss difference (FW − naive), MW/day | −617 | −617 |
| DM statistic | −11.68 | −7.53 |
| p-value (two-sided) | < 0.001 | < 0.001 |

**Result:** LightGBM FW is significantly more accurate than the seasonal naive forecast
on underlying demand at both lags (p < 0.001). LightGBM FW achieves 48% lower daily MAE
than naive_d7 (664 vs 1 281 MW).

This confirms the finding from EXP-004 (reported in `docs/results/forecasting_report.md`)
with formal statistical backing.

_Note: the lag-1 DM statistic was previously reported as −11.67; the script value is −11.6788,
which rounds to −11.68. The conclusion (p < 0.001) is unchanged._

### 2.2 LightGBM FW vs NESO — net demand (ND)

| Model | Daily MAE (MW) |
|-------|:--------------:|
| LightGBM FW (ND) | 995 |
| NESO day-ahead | 653 |

| Statistic | Lag = 1 | Lag = 7 |
|-----------|--------:|--------:|
| Mean loss difference (FW − NESO), MW/day | +342 | +342 |
| DM statistic | +17.15 | +15.15 |
| p-value (two-sided) | < 0.001 | < 0.001 |

**Result:** NESO is significantly more accurate than LightGBM FW on net demand (p < 0.001)
at both lags. LightGBM FW has 52% higher daily MAE on ND than NESO (995 vs 653 MW).

The sign (positive DM) confirms the difference is statistically significant, not just
numerically larger by chance. The claim in EXP-004 is now formally supported: "our model
is better than standard baselines but worse than NESO on ND."

_Note: the lag-1 DM statistic was previously reported as +17.13; the script value is +17.1536,
which rounds to +17.15. The conclusion (p < 0.001) is unchanged._

---

## 3. Battery arm comparisons — Holm correction (EXP-006)

### 3.1 Background

EXP-006 compared six battery-dispatch arms:
- **none** (no battery)
- **A** (fixed dispatch rule)
- **B** (point forecast + LP)
- **B_plus** (point + LP + CQR intervals, no CVaR)
- **C_minus** (quantile scenarios + LP, no CVaR risk weighting)
- **C** (calibrated quantiles + CVaR objective)
- **oracle** (perfect-foresight bound)

Pre-registered success criteria (D-035): H1 (mean cost C < B), H2 (p95 cost C < B),
H3 (mean cost C < none). Existing bootstrap results (D-038): H1 met; H2 not met.

This section applies Holm-Bonferroni correction to the available C-vs-B bootstrap CIs.
H3 (C vs none) cannot be tested because the C-vs-none bootstrap is not in the saved
outputs. Only C vs B is tested here.

**Cost metric:** stylised daily cost index (not £) = daily peak load (MW)
+ 2 × energy shortfall above threshold (MWh) + small throughput term. Units ≈ MW.
See `docs/results/optimisation_report.md` §1 for the full definition.

**Script input:** `outputs/optimisation/c_vs_b_bootstrap.csv` (read-only).

### 3.2 C-vs-B bootstrap CIs and estimated p-values

P-values are **approximate (normal approximation)**: SE ≈ (CI_hi − CI_lo) / (2 × 1.96);
z = diff / SE; p_two = 2(1 − Φ(|z|)). These are illustrative; the bootstrap CI itself
is the primary inferential statement.

| Setting | Stat | C−B diff (MW, cost index) | 95% CI | p-value (approx.) |
|---------|------|:------------------------:|:------:|:-----------------:|
| Historical 2024-25 | mean | −68.7 | [−124.9, −24.6] | 0.0072 |
| Historical 2024-25 | p95 | −21.4 | [−595.6, +186.1] | 0.91 |
| Holistic 2035 | mean | −20.1 | [−50.9, +20.5] | 0.27 |
| Holistic 2035 | p95 | −315.2 | [−590.1, +508.1] | 0.26 |
| Holistic 2035 fast elec. | mean | −34.5 | [−78.7, +7.4] | 0.12 |
| Holistic 2035 fast elec. | p95 | +368.5 | [−570.1, +465.9] | 0.16 |
| Holistic 2050 | mean | +35.9 | [−81.1, +204.9] | 0.62 |
| Holistic 2050 | p95 | −569.6 | [−1239.0, +727.4] | 0.26 |
| Electric 2050 | mean | −105.2 | [−212.1, −19.2] | 0.033 |
| Electric 2050 | p95 | −574.5 | [−925.7, +700.5] | 0.17 |

_Note: Electric 2050 mean p-value was previously reported as 0.032; script value is 0.0325,
rounds to 0.033. Conservative-family conclusion (rank 2, threshold 0.006) is unchanged._

### 3.3 Holm correction

**Pre-specified family (H1, H2, H3 from D-035) — 3 hypotheses; H3 not testable:**

H3 (mean cost C < none) is in the pre-specified family but cannot be tested because the
C-vs-none bootstrap output is not in the saved files. The family therefore has m = 3
pre-specified tests, of which 2 are testable. The Holm threshold for the first test is
α/m = 0.05/3 = 0.0167.

| Rank | Hypothesis | p-value (approx.) | Holm threshold (α/m−k+1) | Reject H0? |
|:----:|-----------|:-----------------:|:------------------------:|:----------:|
| 1 | H1: Historical 2024-25 mean C < B | 0.0072 | 0.05/3 = 0.0167 | **Yes** |
| 2 | H2: Historical 2024-25 p95 C < B | 0.91 | 0.05/2 = 0.025 | No |
| 3 | H3: mean cost C < none (not tested) | — | 0.05/1 = 0.05 | — |

H1 (mean cost improvement) survives Holm correction at α = 0.05 with the full
pre-specified family of m = 3 (threshold 0.0167 > 0.0072). H2 (tail cost) is not
significant (p = 0.91). H3 is not testable.

H1 also survives Holm correction when the family is treated as m = 2 (H1 and H2 only;
threshold 0.025 > 0.0072).

**Conservative family (all 10 C-vs-B tests) — Holm correction:**

| Rank | Setting | Stat | p-value (approx.) | Holm threshold | Reject H0? |
|:----:|---------|------|:-----------------:|:--------------:|:----------:|
| 1 | Historical 2024-25 | mean | 0.0072 | 0.05/10 = 0.005 | No |
| 2 | Electric 2050 | mean | 0.033 | 0.05/9 = 0.006 | No |
| 3–10 | (all others) | — | ≥ 0.12 | ≥ 0.007 | No |

No test survives Holm correction when all 10 comparisons are used as the family.
H1 (p = 0.0072) falls just above the corrected threshold (0.005).

### 3.4 Interpretation

- **Using the pre-specified family (H1, H2, H3; m = 3):** H1 is statistically significant
  (p = 0.0072 < Holm threshold 0.0167). This is consistent with and formally supports the
  original EXP-006 finding (D-038): "mean-cost gain is significant" based on a CI that
  excludes zero. H2 is not significant. H3 is not testable from saved outputs.
- **Using a conservative family of all 10 tests:** No test is significant after correction.
  EXP-006 was designed with historical 2024-25 as the primary setting; the 9 additional
  comparisons include future scenarios not part of the original success criteria.
- **Recommendation:** The more defensible inference is from the pre-specified family.
  The write-up should state that H1 is significant (p = 0.0072 before Holm; p < 0.0167
  Holm threshold with m = 3) and that H2 is not, noting that the normality approximation
  for p-values is an additional assumption beyond the bootstrap CIs.

---

## 4. Summary of findings

| Test | Result |
|------|--------|
| DM: LightGBM FW vs naive_d7 (underlying demand) | Significant: FW significantly better (p < 0.001, DM = −11.68, lag=1) |
| DM: LightGBM FW vs NESO (ND) | Significant: NESO significantly better (p < 0.001, DM = +17.15, lag=1) |
| Holm (H1, H2; m=2 or m=3): mean cost C vs B, real data | H1 significant (p = 0.0072 < threshold 0.0167–0.025); H2 not (p = 0.91) |
| Holm (all 10): C vs B across all settings | No test significant after full-family correction |

These results are consistent with and strengthen the existing reported findings from
Batch 4 and Batch 6. No finding is reversed.

---

## 5. Numbers that changed from the previous version of this document

| Item | Previous value | Script value | Note |
|------|:--------------:|:------------:|------|
| DM(FW vs naive, lag=1) | −11.67 | −11.68 | −11.6788 rounded to 2dp |
| DM(FW vs NESO, lag=1) | +17.13 | +17.15 | +17.1536 rounded to 2dp |
| Electric 2050 mean p | 0.032 | 0.033 | 0.0325 rounded to 3dp |
| Cost unit label | £/MWh/day | MW (cost index) | Corrected; see §3.1 |
| DM at lag=7 | (not reported) | −7.53 / +15.15 | Added |
| Pre-specified family size | m=2 (H1, H2) | m=3 (H1, H2, H3) | H3 not testable |
| H1 Holm threshold | 0.025 | 0.0167 | Corrected for m=3 |
