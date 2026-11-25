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
2. **Battery optimisation arm comparisons** (Batch 6 / EXP-006): pre-registered
   hypothesis assessment (H1, H2, H3) and exploratory Holm-corrected p-values
   derived from the existing block-bootstrap CIs (C vs B, all settings).

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

## 3. Battery arm comparisons — hypothesis assessment (EXP-006)

### 3.1 Background

EXP-006 compared six battery-dispatch arms:
- **none** (no battery)
- **A** (fixed dispatch rule)
- **B** (point forecast + LP)
- **B_plus** (calibrated median + LP, no CVaR)
- **C_minus** (point forecast × unconditional error quantiles + CVaR LP)
- **C** (calibrated conditional quantiles + CVaR LP)
- **oracle** (perfect-foresight bound)

**Pre-registered success criteria (D-035), exact text from `configs/optimisation.yaml`:**
- **H1:** "Setting H: C has lower 95th-percentile daily cost AND lower total shortfall
  than B, with mean daily cost at most 1% higher than B."
- **H2:** "Decomposition, reported whatever the result: C vs B_plus (value of the
  risk-aware decision rule) and C vs C_minus (value of conditional uncertainty)."
  *(H2 is descriptive; not a significance test.)*
- **H3:** "Setting F: C has lower 95th-percentile daily cost than B in at least 3 of
  the 4 future cases."

**Cost metric:** stylised daily cost index (not £) = daily peak load (MW)
+ 2 × energy shortfall above threshold (MWh) + small throughput term. Units ≈ MW.
See `docs/results/optimisation_report.md` §1 for the full definition.

**Script input:** `outputs/optimisation/c_vs_b_bootstrap.csv` (read-only).

---

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

---

### 3.3 Pre-registered hypothesis assessment (H1, H2, H3)

#### H1

H1 is a **conjunction** requiring all three sub-conditions simultaneously:

**Sub-condition 1 — p95 daily cost (Setting H):**
- Point estimate: C−B = −21 MW (C appears cheaper at the 95th percentile)
- 95% CI: [−596, +186] MW — **includes zero**
- p ≈ 0.91 (approximate)
- **Sub-condition 1 not statistically supported.**

**Sub-condition 2 — total shortfall (Setting H):**
- 7-day moving-block bootstrap (n = 663 days, seed = 42, N = 1 000 replicates)
- Script result: CI = [−24.1, +0.2] GWh — **includes zero (barely)**
- **Sub-condition 2 not statistically supported.**
  _(Note: Batch 6 optimisation_report.md reports [−24.3, +0.3] GWh from a slightly
  different bootstrap implementation; conclusion is the same in both cases.)_

**Sub-condition 3 — mean cost ≤ B + 1%:**
- C−B mean = −69 MW; CI [−125, −25] MW — CI excludes zero
- Sub-condition met. This is a _constraint_ in H1 (C must not be much more expensive on
  average), not the primary H1 criterion. The mean-cost gain itself is an exploratory
  secondary finding; see §3.4.

**H1 verdict:** **Not statistically supported.** The p95 component (p ≈ 0.91) and the
shortfall component (CI includes 0) both fail. H1 is met on point estimates only.

#### H2

H2 is a decomposition, not a significance test. Reported whatever the result:
- **C vs B+, mean cost (value of the risk-aware decision rule):** −71 [−158, −16] MW.
  CI excludes 0 — the risk-aware rule is the primary driver. *(Exploratory secondary.)*
- **C vs C−, mean cost (value of conditional uncertainty):** −19 [−47, +13] MW.
  CI includes 0 — conditional calibrated quantiles add no detectable value over an
  unconditional error distribution.

H2 conclusion: C's gain comes from the risk-aware decision rule (B+ vs B+), not from
conditional quantile calibration. This is a descriptive decomposition; no significance
threshold applies.

#### H3

H3 requires C to have lower p95 daily cost than B in at least 3 of the 4 future cases.

| Future case | C−B p95 (MW) | 95% CI | C better (point)? | CI includes 0? |
|-------------|:------------:|:------:|:-----------------:|:--------------:|
| Holistic 2035 | −315 | [−590, +508] | Yes | Yes |
| Holistic 2035 fast elec. | +369 | [−570, +466] | No | Yes |
| Holistic 2050 | −570 | [−1 239, +727] | Yes | Yes |
| Electric 2050 | −575 | [−926, +701] | Yes | Yes |

Point estimate: **3 of 4** future cases favour C → H3 met on point estimates.
All 4 future-case p95 CIs include 0 → **H3 not statistically supported.**

(H3 is not testable using DM or Holm: future settings use synthetic forecasts; no daily time
series are available for formal testing. Assessment is from bootstrap CIs alone.)

---

### 3.4 Secondary exploratory: mean-cost Holm correction (5 comparisons)

**⚠️ This section is EXPLORATORY and SECONDARY. The mean-cost gain is NOT H1.** H1 is the
p95 AND shortfall AND mean≤B+1% conjunction assessed in §3.3 above.

The mean daily cost of C is lower than B in 4 of 5 settings on point estimates. We apply
Holm-Bonferroni over all 5 mean-cost C-vs-B comparisons as a secondary exploratory family.
P-values are **approximate (normal approximation from 95% bootstrap CI)**.

| Rank | Setting | C−B mean (MW) | 95% CI | p (approx.) | Holm threshold (α/m−k+1) | Reject H₀? |
|:----:|---------|:-------------:|:------:|:-----------:|:------------------------:|:----------:|
| 1 | Historical 2024-25 | −69 | [−125, −25] | 0.0072 | 0.010 | **Yes** |
| 2 | Electric 2050 | −105 | [−212, −19] | 0.033 | 0.0125 | No |
| 3 | Holistic 2035 fast elec. | −35 | [−79, +7] | 0.12 | 0.0167 | No |
| 4 | Holistic 2035 | −20 | [−51, +21] | 0.27 | 0.025 | No |
| 5 | Holistic 2050 | +36 | [−81, +205] | 0.62 | 0.050 | No |

**Result:** Only the Historical 2024-25 mean-cost gain (p ≈ 0.0072) survives Holm correction
across the 5-comparison exploratory family (α/5 = 0.010 > 0.0072). No future-case mean-cost
gain survives correction.

**This is an exploratory secondary finding.** It was not part of the pre-registered H1-H3
success criteria in D-035. It may be reported as a secondary result, clearly labelled as
exploratory, and may not be reported as a confirmed hypothesis or as evidence for H1.

---

### 3.5 Conservative Holm (all 10 C-vs-B tests; exploratory)

| Rank | Setting | Stat | p-value (approx.) | Holm threshold | Reject H0? |
|:----:|---------|------|:-----------------:|:--------------:|:----------:|
| 1 | Historical 2024-25 | mean | 0.0072 | 0.05/10 = 0.005 | No |
| 2 | Electric 2050 | mean | 0.033 | 0.05/9 = 0.006 | No |
| 3–10 | (all others) | — | ≥ 0.12 | ≥ 0.007 | No |

No test survives Holm correction when all 10 comparisons are used as the family.
The exploratory mean-cost finding (p = 0.0072) falls just above the corrected
threshold (0.005) in this conservative family.

---

### 3.6 Interpretation

- **H1 (pre-registered primary):** Not statistically supported. The p95 component
  (p ≈ 0.91) and the shortfall component (CI barely includes 0) both fail. H1 is met
  on point estimates only. No sentence in this document or in associated reports should
  state "H1 is statistically significant" or "H1 is confirmed."

- **H2 (pre-registered; descriptive):** The main source of C's gain is the risk-aware
  decision rule, not conditional quantile calibration. No significance threshold applies
  to H2.

- **H3 (pre-registered):** 3 of 4 future-case p95 point estimates favour C; all 4 CIs
  include 0. H3 met on point estimates only; not statistically supported.

- **Secondary exploratory finding:** The historical 2024-25 mean-cost gain (C−B = −69 MW,
  CI [−125, −25] MW) survives Holm correction across 5 mean-cost comparisons (p ≈ 0.007,
  threshold 0.010). This is **not H1**; it is a secondary exploratory result. It may be
  stated as: "The mean daily cost gain from uncertainty-aware scheduling is statistically
  detectable on historical 2024-25 data (exploratory secondary finding, p ≈ 0.007,
  Holm-corrected across 5 mean-cost comparisons; approximate p-value from bootstrap CI)."

- **Conservative family (all 10 tests):** No test survives when all 10 C-vs-B comparisons
  form the correction family (§3.5).

---

## 4. Summary of findings

| Test | Result |
|------|--------|
| DM: LightGBM FW vs naive_d7 (underlying demand) | Significant: FW significantly better (p < 0.001, DM = −11.68, lag=1) |
| DM: LightGBM FW vs NESO (ND) | Significant: NESO significantly better (p < 0.001, DM = +17.15, lag=1) |
| H1 (pre-registered): p95 AND shortfall AND mean≤B+1% | **Not statistically supported**: p95 CI includes 0 (p≈0.91); shortfall CI includes 0. Met on point estimates only. |
| H2 (pre-registered; descriptive): C vs B+, C vs C− | Risk-aware rule: CI excludes 0. Conditional uncertainty: CI includes 0. Descriptive only. |
| H3 (pre-registered): p95 better in ≥3 of 4 future cases | Met on point estimates (3 of 4); all 4 CIs include 0. Not statistically supported. |
| Exploratory secondary: mean cost C vs B (m=5 Holm) | Historical 2024-25 only survives (p=0.0072 < threshold 0.010). No future case survives. |
| Conservative Holm (all 10 C-vs-B tests) | No test survives after full-family correction |

These results are consistent with the existing reported findings from Batch 4 and Batch 6.
No finding is reversed.

---

## 5. Numbers that changed from the previous version of this document

| Item | Previous value | Script value | Note |
|------|:--------------:|:------------:|------|
| DM(FW vs naive, lag=1) | −11.67 | −11.68 | −11.6788 rounded to 2dp |
| DM(FW vs NESO, lag=1) | +17.13 | +17.15 | +17.1536 rounded to 2dp |
| Electric 2050 mean p | 0.032 | 0.033 | 0.0325 rounded to 3dp |
| Cost unit label | £/MWh/day | MW (cost index) | Corrected; see §3.1 |
| DM at lag=7 | (not reported) | −7.53 / +15.15 | Added |
| Pre-specified family size | m=2 (H1, H2) | m=3 (H1, H2, H3) | H3 not testable from saved outputs; corrected in Stage 9 |
| H1 Holm threshold | 0.025 | 0.0167 | Corrected for m=3 in Stage 9 |
| H1–H3 definitions | H1=mean C<B; H2=p95 C<B; H3=mean C<none | Per configs/optimisation.yaml | **Corrected Stage 11**: definitions were wrong; mean-cost gain relabelled as exploratory secondary |
| "H1 is statistically significant" | Stated in §3.4 | **Removed** | H1 is NOT statistically supported (p95 p≈0.91; shortfall CI includes 0) |
| Exploratory mean-cost Holm (m=5) | Not reported | Added §3.4 | Only Historical 2024-25 mean survives; labelled exploratory |
