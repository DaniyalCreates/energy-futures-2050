# CS-2 Pre-registration: conditional recalibration of prediction intervals

_Status: pre-registered 2026-11-24, branch improve/phase-b._
_No method code has been written or run at the time this document is committed._
_Pre-registration seal: laptop only (Dani's choice). Timing cannot be independently verified by outsiders._

---

## 1. Motivation (from CS-1)

CS-1 measured empirical coverage of the existing 50/80/90% CQR prediction intervals
(commit 4150027). Key findings for the 90% nominal interval:

| Condition | 2023 coverage | 2024-25 coverage | Nominal |
| --- | --- | --- | --- |
| All half-hours | 92.5% [91.0, 93.8] | 90.5% [89.4, 91.6] | 90% |
| Cold days (obs < 3 °C) | 93.3% [90.6, 95.7] | **80.3% [70.8, 88.4]** | 90% |
| Cold days (fcast < 3 °C) | n/a | **82.6% [72.8, 90.3]** | 90% |
| Top-5% demand days | 93.2% [90.3, 95.9] | **82.5% [74.1, 89.8]** | 90% |
| Winter (Dec–Feb) | 89.6% [86.2, 92.5] | 87.0% [83.8, 90.1] | 90% |
| 2025 (full year) | — | **89.1% [87.7, 90.5]** | 90% |

The cold-day under-coverage does **not** appear in 2023, so it cannot be diagnosed or fixed
using 2023 alone. Because 2024-25 was examined in CS-1, it is no longer a clean test set.
The entire 2022-2025 window is therefore treated as development data.
The one-time confirmation run on 2026 is approved separately.

---

## 2. Development data

| File | Period | Input type | Rows |
| --- | --- | --- | --- |
| `outputs/advanced/validation/quantiles_2022_2023.parquet` | 2022-01-01 – 2023-12-31 | Observed weather (PW) | 35,040 |
| `outputs/advanced/test/quantiles_FW_raw.parquet` | 2024-03-08 – 2025-12-31 | Forecast weather (FW, ~48 h ahead) | 31,872 |
| `data/processed/demand_weather.parquet` | 2009-2025 | Actual demand + observed temperatures | 298,032 |
| `data/raw/weather_forecast/*.json` | 2024-2025 | Archived ~48 h-ahead forecast temperatures | 12 files |
| `outputs/advanced/test/point_underlying_demand.parquet` | 2024-2025 | LightGBM FW point forecasts | 35,088 |

**What is not in development data:** 2026 (reserved for one-time confirmation).

**Important:** the 2022-23 and 2024-25 raw quantiles were produced with different weather
inputs (observed vs ~48 h-ahead forecast). The two segments are used together but this
difference is tracked throughout and labelled in results.

There is a data gap: no quantile predictions exist for 2024-01-01 to 2024-03-07 (67 days)
because the forecast-radiation archive (needed for FW features) begins on 2024-03-07.
Actual demand and observed temperature are available throughout; they inform calibration
thresholds but not the quantile predictions themselves.

---

## 3. What is available at 09:00 D-1 (strict information constraint)

Methods may only condition on the following, which are all known at 09:00 on the day before:

| Feature | 2022-23 | 2024-25 |
| --- | --- | --- |
| Temperature proxy | Previous day's (D−1) **observed** GB mean temperature (best proxy available — no archived forecasts exist for 2022-23) | Archived **forecast** GB mean temperature for day D (`previous_day2`, ~48 h ahead) |
| Predicted demand level | q50 of raw LightGBM quantiles for day D | q50 of raw LightGBM quantiles for day D (= gbm_FW in point file) |
| Calendar flags | bank holiday, day of week, month, season | same |

For 2022-23, using the previous day's observed temperature as a proxy for a forecast
introduces a small upward bias in cold-day identification (observed is slightly more
accurate than a true forecast), so cold-day calibration on 2022-23 may be slightly
optimistic. This is noted as a limitation.

**Outcome-based reporting only:** evaluation reports may additionally show coverage broken
down by the actual observed temperature on day D itself, clearly labelled
"outcome-based cold flag — reporting only". This label is never used in calibration or
method selection.

---

## 4. Candidate methods

All candidates take the **raw LightGBM quantile predictions** (q05/q10/q25/q50/q75/q90/q95)
and actual demand from the calibration window as inputs, and produce calibrated intervals.
The baseline reproduces the current method exactly.

### Baseline — Rolling unconditional CQR (current method)

The correction is recomputed **daily**: for each forecast day D, W_t is the rolling window
of 365 calendar days ending on D−1 (all outcomes known by 09:00 on D−1).

For each half-hour t on day D:

1. Nonconformity score for each calibration point i in W_t:
   `s_i = max(q_lo(x_i) − y_i, y_i − q_hi(x_i))`
   where (q_lo, q_hi) are the raw quantile predictions for the target level
   (e.g., q05 and q95 for the 90% interval).
2. Correction: `c = quantile({s_i : i ∈ W_t}, level = (1 − α)(1 + 1/|W_t|))` with α = 0.1.
3. Calibrated interval: `[q_lo(x_t) − c, q_hi(x_t) + c]`.

The baseline must reproduce the CS-1 overall coverage numbers (±0.5 pp) in the
rolling evaluation as a sanity check; if it does not, a bug is assumed and must be fixed
before proceeding.

### Candidate A — Mondrian CQR (condition-specific corrections)

Same CQR formula as the baseline, but the correction is computed separately per stratum.
Strata are assigned at 09:00 D-1 using only information then available.

**Stratification (priority-ordered, mutually exclusive — one stratum per day):**

1. **Cold**: temperature proxy for day D < 3 °C.
2. **High predicted demand**: temperature proxy ≥ 3 °C AND the daily maximum q50 for day D
   is ≥ the 95th percentile of daily-maximum q50 values over W_t.
3. **Normal**: all remaining days.

Each stratum calibrates independently using only calibration points from that stratum in W_t.
Calibration days in W_t are assigned to strata with the same priority rule, using their own
temperature proxy and the 95th-percentile threshold computed over the current W_t.
The correction for a half-hour t inherits the stratum of its calendar day D.

**Minimum sample size (pre-declared):** if a stratum contains fewer than `min_days = 20`
calibration days in W_t, fall back to the global (unconditional) baseline calibration
for that day. This prevents unstable corrections when cold days are rare in the
rolling window.

### Candidate B — Width-normalised conformal scores (global)

Replace the standard CQR nonconformity score with a width-normalised version:

`s_i = max(q_lo(x_i) − y_i, y_i − q_hi(x_i)) / (q_hi(x_i) − q_lo(x_i))`

The correction c is the (1 − α)(1 + 1/|W_t|) quantile of these normalised scores.
The calibrated interval is then:

`[q_lo(x_t) − c · (q_hi(x_t) − q_lo(x_t)), q_hi(x_t) + c · (q_hi(x_t) − q_lo(x_t))]`

This is global (not condition-specific) and uses the same 365-day rolling window as the baseline.
Rationale: width-normalised scores make the correction scale-invariant; on cold days where the
raw quantiles are wider, the same normalised score implies a proportionally larger absolute
adjustment, which may partially correct the under-coverage.

### Candidate C — Mondrian CQR with extended cold-day window

Uses the same three-stratum priority scheme as Candidate A (cold → high predicted demand →
normal), with one change: the **cold stratum** uses **all available past cold-day data**
(unlimited lookback) rather than the 365-day rolling window. The high-predicted-demand and
normal strata still use the standard 365-day rolling window.

Rationale: with ~22 cold days per year, a 365-day window gives barely enough cold-day
calibration points for a stable correction; pooling all past cold days (e.g., 44–66 from
2 or 3 years) gives a more stable quantile estimate. The same `min_days = 20` fallback
applies to the cold stratum (falls back to global baseline if fewer than 20 past cold days
exist in total, which applies only to early 2023).

---

## 5. Rolling time-series evaluation design

All methods recalibrate **daily**: the correction for each forecast day D is computed fresh
using only outcomes known by 09:00 on D−1 (the rolling window described in §4).
**Quarters are reporting units only** — they are used to group and display results, not as
recalibration points. Coverage statistics for each quarter are pooled over all half-hours
within that quarter's evaluation days.

**Evaluation quarters (11 total):**

| # | Period | Calibration data available |
| --- | --- | --- |
| 1 | 2023-Q1 (Jan–Mar 2023) | All of 2022 |
| 2 | 2023-Q2 (Apr–Jun 2023) | 2022 + Q1 2023 |
| 3 | 2023-Q3 (Jul–Sep 2023) | 2022 + Q1–Q2 2023 |
| 4 | 2023-Q4 (Oct–Dec 2023) | 2022 + Q1–Q3 2023 |
| 5 | 2024-Q2 (Apr–Jun 2024) | 2022–2023 + 2024-03-08–Mar-31 |
| 6 | 2024-Q3 (Jul–Sep 2024) | 2022–2023 + 2024 through Jun |
| 7 | 2024-Q4 (Oct–Dec 2024) | 2022–2023 + 2024 through Sep |
| 8 | 2025-Q1 (Jan–Mar 2025) | 2022–2024 |
| 9 | 2025-Q2 (Apr–Jun 2025) | 2022–2024 + Q1 2025 |
| 10 | 2025-Q3 (Jul–Sep 2025) | 2022–2024 + Q1–Q2 2025 |
| 11 | 2025-Q4 (Oct–Dec 2025) | 2022–2024 + Q1–Q3 2025 |

**Note:** 2024-Q1 (Mar 8–Mar 31, only 24 days) is used in the calibration set for
subsequent quarters but is **not** an evaluation quarter (too short to report
meaningful conditional coverage statistics). 2024 evaluation therefore starts at Q2.

**Temperature type per quarter:**
- Quarters 1–4 (2023): previous day's observed temperature (PW inputs). Cold label = previous day's observed temp < 3 °C.
- Quarters 5–11 (2024-25): archived forecast temperature (FW inputs, previous_day2). Cold label = forecast temp < 3 °C.
- In the calibration set, the same rule applies: previous day's observed temp for 2022-23 observations,
  archived forecast temp for 2024-25 observations. The transition is applied consistently.

---

## 6. Metrics

Computed over all evaluation quarters combined (pooled across the full rolling window),
and also broken down by quarter and by condition. Block-bootstrap 95% CIs by calendar day,
1,000 resamples, seed 42.

### 6.1 Primary metrics (used for selection)

| Metric | Definition |
| --- | --- |
| **Coverage_90** | Fraction of half-hours where actual demand ∈ [calibrated q05, calibrated q95] |
| **Coverage_90 (cold)** | As above, restricted to cold-day half-hours |
| **Coverage_90 (high predicted demand)** | As above, restricted to half-hours on days where the daily maximum q50 ≥ 95th percentile of daily-maximum q50 over the full evaluation window |
| **Width_90** | Mean of (calibrated q95 − calibrated q05) across all half-hours (MW) |

### 6.2 Secondary metrics (reported but not used for selection)

| Metric | Definition |
| --- | --- |
| Coverage_80, Coverage_50 | As above for 80% and 50% intervals |
| Coverage_90 (winter) | Restricted to Dec–Feb half-hours |
| Coverage_90 (bank holiday) | Restricted to bank-holiday half-hours |
| Interval score (Winkler) | `(q95−q05) + 20·max(q05−y,0) + 20·max(y−q95,0)` per half-hour, mean over all |
| Pinball loss | Mean of pinball at τ ∈ {0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95} |

---

## 7. Pre-declared selection criteria

The winning method is chosen by the following rules, evaluated on the rolling
out-of-sample results (all 11 quarters, pooled). Rules are applied in order:

1. **Coverage guard (necessary condition):** overall Coverage_90 must be in **[87%, 93%]**.
   Any method outside this band is disqualified regardless of other metrics.

2. **Cold-day improvement (necessary condition):** Coverage_90 (cold) must be at least
   **3.0 percentage points higher** than the baseline's Coverage_90 (cold) (pooled point
   estimate). Methods failing this threshold are disqualified.

3. **High-demand improvement (necessary condition):** Coverage_90 (high predicted demand)
   must be at least **3.0 percentage points higher** than baseline (pooled point estimate).
   Methods failing this threshold are disqualified.

4. **Width guard (necessary condition):** Width_90 must be ≤ 1.25 × baseline Width_90.
   Methods that increase average interval width by more than 25% are disqualified.

5. **Selection among remaining candidates:** choose the method minimising
   `max(|Coverage_90(cold) − 90|, |Coverage_90(high predicted demand) − 90|)` —
   i.e., the method whose worst conditional coverage is closest to the 90% nominal target.
   Break ties by lower mean interval score (Winkler, §6.2).

6. **If no candidate passes all four conditions:** retain the baseline (current method),
   report the finding, and do not proceed to the 2026 confirmation run with a new method.
   Dani must approve any next step separately.

---

## 8. Procedure after this pre-registration is committed

1. **CS-2a (implementation):** Write method code and rolling evaluation script.
   Commit to `improve/phase-b` **before running anything**.

2. **CS-2b (run):** Run the rolling evaluation. Record all results (all 11 quarters,
   all 4 methods, all metrics) in `outputs/v2_cs2_rolling/`.

3. **CS-2c (selection):** Apply the selection criteria in §7 to the recorded results.
   The selected method is frozen; no further tuning is permitted after seeing results.
   Record outcome in `docs/research_changelog.md`.

4. **CS-2d (report):** Write `docs/results/conditional_calibration.md` summarising the
   rolling evaluation, the selection decision, and the rationale.

5. **CS-3 (confirmation, approved separately by Dani):** Apply the original baseline AND
   the selected method once to the 2026 data (Jan–Oct 2026). Co-primary metrics:
   Coverage_90 on Jan–Feb 2026 half-hours (the only winter months in the window) and
   Coverage_90 on high-predicted-demand days. Cold-day coverage (< 3 °C) is computed
   and reported but treated as **descriptive only**, because the Jan–Oct window is expected
   to contain too few cold days for a well-powered test. The exact pass criteria for the
   2026 run will be written in a separate **CS-3 protocol document** and committed before
   any 2026 data is downloaded or opened. This step requires Dani's explicit approval.

---

## 9. Limitations to state in write-ups

- Development data includes 2024-25 (examined in CS-1); the rolling evaluation is
  time-series-honest but results are not independent of CS-1 observations.
- Temperature for 2022-23 calibration is observed rather than forecast; Mondrian and
  extended-window methods may be slightly optimistic on cold-day calibration in those years.
- The 2026 confirmation window (Jan–Oct) covers only January and February as winter months;
  statistical power for cold-day coverage specifically is limited.
- In a 365-day rolling calibration window, the cold stratum will often contain fewer than
  20 days (especially in the 2023 quarters), causing Candidate A to fall back to the global
  baseline correction for cold days on those quarters. This limits Candidate A's ability to
  improve cold-day coverage over the early part of the evaluation.
- Pre-registration seal: laptop only. Timing cannot be independently verified.

---

## 10. Prohibitions

- Do not access, download, or open 2026 data before the confirmation run is approved.
- Do not adjust candidate methods, strata definitions, thresholds, or selection criteria
  after viewing any CS-2 results.
- Do not modify `outputs_archive/v1_5db4552/`.
- Do not commit to `main` or push to GitHub.

---

## 11. Amendment 1 (2026-11-24, before any CS-2 code or results)

**Timing correction found in external review. No code or results existed at the time of
this amendment.**

At 09:00 on D-1 only days ending by D-2 are fully observed. The existing rolling CQR
uses `task.train_cutoff(D)` = 09:00 local D-1 − 30-min publication lag − 30-min period
= **08:00 local on D-1**; the last half-hour in the window is the 08:00–08:30 slot on
D-1, so the last fully observed calendar day is **D-2**.

Therefore:

(i) **Calibration window W_t ends at D-2** (the last day fully known at issue time),
matching the existing CQR cutoff. References to "ending D-1" in §3, §4, and §5 are
superseded by this.

(ii) **2022-23 temperature proxy is the D-2 observed GB daily mean temperature**, not
D-1 as stated in §3. D-1 observed temperature is not fully available at 09:00 on D-1
(only the first ~8.5 hours have elapsed).

These override §3, §4, and §5 where they conflict. **Reason:** timing error found in
external review; no code or results existed.
