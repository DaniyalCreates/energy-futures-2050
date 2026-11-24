# CS-4: Statistical significance tests on frozen results

_Branch: improve/phase-b | Date: 2026-11-24_
_All inputs from: outputs/advanced/test/ and outputs/optimisation/ (frozen after Batch 8)._
_No 2026 data accessed. No models retrained._

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

**Method:** Diebold-Mariano (1995) test with Newey-West HAC variance (lag = 1 on
daily aggregates). Losses aggregated to daily mean absolute error (MAE) before the
test, to reduce within-day autocorrelation. Evaluation window: 2024-03-08..2025-12-31
(fw_comparison_start, n = 664 calendar days). Two-sided tests.

### 2.1 LightGBM FW vs naive_d7 — underlying demand

| Model | Daily MAE (MW) |
|-------|:--------------:|
| LightGBM FW | 664 |
| naive_d7 | 1 281 |

| Statistic | Value |
|-----------|------:|
| Mean loss difference (FW − naive) | −617 MW/day |
| DM statistic | −11.67 |
| p-value (two-sided) | < 0.001 |

**Result:** LightGBM FW is significantly more accurate than the seasonal naive forecast
on underlying demand (p < 0.001). LightGBM FW achieves 48% lower daily MAE than
naive_d7 (664 vs 1 281 MW).

This confirms the finding from EXP-004 (reported in `docs/results/forecasting_report.md`)
with formal statistical backing.

### 2.2 LightGBM FW vs NESO — net demand (ND)

| Model | Daily MAE (MW) |
|-------|:--------------:|
| LightGBM FW (ND) | 995 |
| NESO day-ahead | 653 |

| Statistic | Value |
|-----------|------:|
| Mean loss difference (FW − NESO) | +342 MW/day |
| DM statistic | +17.13 |
| p-value (two-sided) | < 0.001 |

**Result:** NESO is significantly more accurate than LightGBM FW on net demand (p < 0.001).
LightGBM FW has 52% higher daily MAE on ND than NESO (995 vs 653 MW).

The sign (positive DM) confirms our model is significantly worse than NESO on ND, not
just numerically larger by chance. This is consistent with NESO's operational advantage
(better weather inputs, more sophisticated features, real-time corrections). The claim
in EXP-004 is now formally supported: "our model is better than standard baselines but
worse than NESO on ND."

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
Only C vs B is tested here (not C vs none, as the latter bootstrap is not in the saved
outputs).

### 3.2 C-vs-B bootstrap CIs and estimated p-values

P-values estimated from the 95% bootstrap CI under a normality approximation:
SE ≈ (CI_hi − CI_lo) / (2 × 1.96); z = diff / SE; p_two = 2(1 − Φ(|z|)).

| Setting | Stat | C−B diff (£/MWh/day) | 95% CI | p-value (est.) |
|---------|------|:--------------------:|:------:|:--------------:|
| Historical 2024-25 | mean | −68.7 | [−125, −25] | 0.007 |
| Historical 2024-25 | p95 | −21.4 | [−596, +186] | 0.91 |
| Holistic 2035 | mean | −20.1 | [−51, +21] | 0.27 |
| Holistic 2035 | p95 | −315.2 | [−590, +508] | 0.26 |
| Holistic 2035 fast elec. | mean | −34.5 | [−79, +7] | 0.12 |
| Holistic 2035 fast elec. | p95 | +368.5 | [−570, +466] | 0.16 |
| Holistic 2050 | mean | +35.9 | [−81, +205] | 0.62 |
| Holistic 2050 | p95 | −569.6 | [−1239, +727] | 0.26 |
| Electric 2050 | mean | −105.2 | [−212, −19] | 0.032 |
| Electric 2050 | p95 | −574.5 | [−926, +700] | 0.17 |

### 3.3 Holm correction

**Primary family (H1 and H2 from D-035) — 2 tests:**

| Rank | Hypothesis | p-value | Holm threshold (α/m−k+1) | Reject H0? |
|:----:|-----------|:-------:|:------------------------:|:----------:|
| 1 | H1: Historical 2024-25 mean C < B | 0.007 | 0.05/2 = 0.025 | **Yes** |
| 2 | H2: Historical 2024-25 p95 C < B | 0.91 | 0.05/1 = 0.050 | No |

H1 (mean cost improvement) survives Holm correction at α = 0.05 when the family
is restricted to the two pre-registered hypotheses (H1 and H2). H2 (tail cost) is
not significant (p = 0.91).

**Conservative family (all 10 C-vs-B tests) — Holm correction:**

| Rank | Setting | Stat | p-value | Holm threshold | Reject H0? |
|:----:|---------|------|:-------:|:--------------:|:----------:|
| 1 | Historical 2024-25 | mean | 0.007 | 0.05/10 = 0.005 | No |
| 2 | Electric 2050 | mean | 0.032 | 0.05/9 = 0.006 | No |
| 3–10 | (all others) | — | ≥ 0.12 | ≥ 0.007 | No |

No test survives Holm correction when the full family of 10 comparisons (all settings
and stats) is used. The first test (p = 0.007) falls just above the corrected threshold
(0.005).

### 3.4 Interpretation

- **Using the pre-specified family (H1, H2):** H1 is statistically significant. This is
  consistent with and formally supports the original EXP-006 finding (D-038): "mean-cost
  gain is significant" based on a CI that excludes zero.
- **Using a conservative family of all 10 tests:** No test is significant after correction.
  This is not surprising: EXP-006 was designed with historical 2024-25 as the primary
  setting; the 9 additional comparisons include future scenarios not part of the original
  success criteria.
- **Recommendation:** The more defensible inference is from the pre-specified family.
  The dissertation and KTP report should state that H1 is significant (p = 0.007 before
  Holm; p < 0.025 Holm threshold) and that H2 is not, noting that the normality
  approximation for p-values is an additional assumption beyond the bootstrap CIs.

---

## 4. Summary of findings

| Test | Result |
|------|--------|
| DM: LightGBM FW vs naive_d7 (underlying demand) | Significant: FW significantly better (p < 0.001, DM = −11.67) |
| DM: LightGBM FW vs NESO (ND) | Significant: NESO significantly better (p < 0.001, DM = +17.13) |
| Holm (H1, H2): mean cost C vs B, real data | H1 significant (p = 0.007 < threshold 0.025); H2 not (p = 0.91) |
| Holm (all 10): C vs B across all settings | No test significant after full-family correction |

These results are consistent with and strengthen the existing reported findings from
Batch 4 and Batch 6. No finding is reversed.
