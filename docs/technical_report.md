# Uncertainty-Aware Forecasting and Risk-Aware Flexibility Planning for Great Britain's Electricity System

**Technical research report · Energy Futures 2050 · Daniyal Tariq · November 2026**

_All results come from experiments in this repository. Each table cites the experiment (EXP-00x, `EXPERIMENT_LOG.md`) and the command that regenerates it. Protocols for the forecasting test (EXP-004) and the decision experiment (EXP-006) were committed before the corresponding data were used._

---

## Abstract

Electricity systems are electrifying heat and transport while relying more on weather-dependent generation, so flexibility decisions (when to charge and discharge storage, when to shift demand) are made under growing uncertainty. This project asks whether **uncertainty-aware machine learning, combined with scenario simulation and constrained optimisation, makes flexibility planning more robust than conventional forecasting and deterministic decisions**, using Great Britain as a case study.

We built an open, reproducible pipeline:
1. A leakage-tested day-ahead forecaster of GB half-hourly demand (LightGBM) with conformally calibrated quantiles.
2. A scenario engine translating NESO Future Energy Scenarios (FES) 2025 into half-hourly 2030–2050 demand and net demand across 13 historical weather years.
3. A linear-programming battery scheduler compared across six pre-registered decision methods.

On held-out 2024–25 data, the forecaster reaches 664 MW mean absolute error (2.2%), 48% better than a seasonal-naive baseline. Its calibrated 90% intervals cover 90.5% of outcomes. It remains **52% less accurate than NESO's operational forecast**.

In the decision experiment, forecast-driven optimisation captures 61% of perfect-foresight battery value, against 38% for a fixed rule. Uncertainty-aware (CVaR) scheduling captures 64%. Its average-cost improvement is statistically significant as an **exploratory secondary finding** (not a pre-registered outcome), but **its tail-risk improvement is not**. The main levers are optimising at all and forecast accuracy; risk-awareness is a smaller, consistent addition that grows when storage is scarce.

---

## 1. Problem and research question

Flexibility assets earn their value at peaks and during stress, exactly when forecasts are least reliable. Planners usually commit to schedules from point forecasts (deterministic decisions). Probabilistic forecasting and stochastic or risk-averse optimisation promise better decisions under uncertainty, but whether that promise holds at GB system scale, with real forecasts and honest baselines, is an empirical question.

**Primary question:** can uncertainty-aware ML plus scenario simulation and constrained optimisation improve the robustness of electricity flexibility planning compared with conventional forecasting and deterministic decision-making?

**Scope:** an aggregated GB system-level prototype. It is not a network model and not a digital twin; the 2050 results are explorations, not predictions.

## 2. Related work (brief)

- **Probabilistic load forecasting** is well established. Hong & Fan (2016) review methods and evaluation; proper scoring rules (Gneiting & Raftery, 2007) underpin the pinball-loss evaluation used here. Gradient boosting (LightGBM: Ke et al., 2017) is a strong tabular baseline.
- **Conformal calibration:** conformalised quantile regression (Romano, Patterson & Candès, 2019) gives distribution-free coverage. Adaptive or rolling variants address non-stationarity (Gibbs & Candès, 2021).
- **Decision-making under uncertainty:** CVaR optimisation (Rockafellar & Uryasev, 2000) linearises tail-risk objectives. Decision-focused learning reviews (Mandi et al., 2024; for power systems, arXiv:2401.03680) note that better forecast accuracy does not guarantee better decisions. Studies of PV-plus-battery scheduling report that the added value of probabilistic forecasts can be small.
- **Long-term scenarios:** NESO FES 2025 provides the authoritative GB pathways used here.

**Positioning:** most decision-value studies work at household, microgrid or plant scale. This work contributes an **open, reproducible GB system-level benchmark** that (i) compares against the system operator's real day-ahead forecast, (ii) separates forecast type from decision method in a six-arm design, and (iii) stress-tests decisions on FES-based futures. It is an applied, incremental contribution, not a new method.

## 3. Data

| Source | Use | Coverage | Licence |
| --- | --- | --- | --- |
| NESO Historic Demand Data | Target, embedded solar and wind | 2009–2025, half-hourly | NESO Open Data Licence |
| NESO Day-Ahead Demand Forecast Performance | Operational benchmark | Apr 2021 on | NESO Open Data Licence |
| NESO FES 2025 (ED1, ES1) | Pathway demand and supply | 2024–2050, annual | NESO Open Data Licence |
| Open-Meteo Historical Weather (ERA5) | Training weather (6 GB cities) | 2009–2025, hourly | CC BY 4.0, non-commercial free tier |
| Open-Meteo Previous Runs | Archived ~48 h weather forecasts | Feb 2024 on | CC BY 4.0, non-commercial free tier |

Cleaning handles 46/50-period clock-change days, mixed date formats, NESO forecast rows and duplicates. Anomalies are flagged, never silently removed; the build stops on any parse failure. A mis-formatted 2023 file removed a whole year in the first build and was caught by this reporting.

**Target: underlying demand** = National Demand + estimated embedded solar + embedded wind. Mean National Demand fell 27% between 2009 and 2025, but underlying demand fell only 17%. About a third of the apparent decline is local generation hiding demand. Dataset v1: 298,032 half-hours, no gaps. Rebuilding it from raw files reproduces it exactly (§8).

## 4. Methods

**4.1 Forecasting task.** Forecasts are issued 09:00 UK time on D-1 for every period of day D. This matches NESO's first publication; NESO actually publishes at 09:30–09:45, so it has slightly more information. Observations count as available 30 minutes after their period ends. Lags come only from D-2, D-7 and D-14, plus the last 24 hours available at issue time. Automated tests check that no feature uses data published after the issue time, across clock changes.

**4.2 Models.** Seasonal-naive (D-7, D-2); linear regression (calendar, ± degree-day weather); LightGBM point and quantile models (5–95%) with fixed hyper-parameters. Weather settings: **PW** observed weather (an upper bound), **NW** no weather, **FW** archived forecasts at inference time (realistic). Validation uses 2023 with monthly expanding-window refits; the test set (2024–25) was used once, after pre-registration (D-023).

**4.3 Calibration.** Rolling conformalised quantile regression: each day's interval correction is the finite-sample quantile of the past 365 days' out-of-sample conformity scores whose outcomes were known at issue time.

**4.4 Scenario engine.** Demand in year Y = 2024 underlying demand (weather year W, rescaled to 2024 energy) + FES changes since 2024, allocated as:
- EV energy: idealised daily valley-filling.
- Residential heat pumps: heating degree-hours ÷ COP, using the Staffell et al. (2012) air-source regression with a 45 °C flow temperature (assumption).
- Electrolysis and data centres: flat.
- Everything else: the historical shape.

Wind and solar are FES energy (generation + curtailment) × historical capacity-factor shapes; nuclear is flat. Annual energy changes match FES exactly (tested). Weather years 2013–2025 provide the uncertainty range.

**4.5 Decision experiment.** At 09:00 on D-1, commit a 24 h schedule for one aggregated battery: power P, energy E, round-trip efficiency 0.88, 50% charge at the start and end of each day. The LP minimises a stylised cost index = daily peak (MW) + 2 × energy above a stress threshold (MWh) + a small throughput cost. Risk-aware arms minimise 0.5·mean + 0.5·CVaR₀.₉₀ over seven comonotonic quantile scenarios.

| Arm | Forecast | Decision |
| --- | --- | --- |
| A | Seasonal naive | Fixed threshold rule |
| B | LightGBM point | Deterministic LP |
| B+ | Calibrated median | Deterministic LP |
| C− | Point × unconditional error quantiles | CVaR LP |
| C | Calibrated conditional quantiles | CVaR LP |
| Oracle | Realised load | Deterministic LP |

Settings: **H**, real forecasts, 8 Mar 2024 – 31 Dec 2025, FES 2024 battery (6.8 GW / 9 GWh). **F**, four FES 2035/2050 cases with synthetic forecasts built from real 2024–25 errors. Success criteria H1–H3 were committed beforehand (D-035). Uncertainty is estimated with a 7-day moving-block bootstrap.

## 5. Results

### 5.1 Forecasting (EXP-001–004)

Test window 8 Mar 2024 – 31 Dec 2025, MAE in MW:

| Model | Underlying demand | National Demand |
| --- | --- | --- |
| Seasonal naive (D-7) | 1,281 | 2,024 |
| Linear + perfect weather | 1,089 | 1,565 |
| LightGBM, no weather | 797 | 1,386 |
| LightGBM, perfect weather (upper bound) | 657 | 968 |
| **LightGBM, forecast weather** | **664 (2.2%)** | **995** |
| **NESO operational** | — | **653** |

- Realistic weather costs only 1% accuracy compared with perfect weather.
- Weather is worth 17% of the error (27% at high demand).
- Errors concentrate on bank holidays (1,039 MW), Christmas (1,120), cold spells below 3 °C (874) and the top 5% of demand (1,000).
- NESO is better in every hour, overnight included, so the gap is not only about solar.

**Calibration (test, forecast weather):**

| Interval | Raw coverage | Calibrated (CQR) coverage |
| --- | --- | --- |
| 50% | 34.4% | 48.8% |
| 80% | 61.4% | 79.6% |
| 90% | 75.2% | 90.5% |

### 5.2 Scenarios (EXP-005)

Holistic Transition peak demand rises by a median **+13.9 GW (2035)** and **+57.3 GW (2050)** across weather years, against FES's +16.0 and +61.7 GW. Holistic and Hydrogen Evolution agree with FES to within about 13%; Electric Engagement and Falling Behind are under-stated. Heat pumps at peak reach 60–75% of FES's value; the EV component does not reproduce FES (an artefact of the idealised profile).

The most demanding condition is a **cold, still week (weather of 9–15 Dec 2022)**. In 2050 Holistic it produces 108 GW peak demand and 81.6 GW peak net demand, with **10.1 TWh** to cover from storage, dispatchable plant or imports in seven days. That is about 36× FES's 2050 battery and long-duration storage energy. EV charging behaviour is the largest lever: 30% unmanaged charging adds 11 GW to the 2035 peak.

### 5.3 Decisions (EXP-006)

Setting H, share of perfect-foresight value captured: **A 37.7% · B 61.3% · B+ 61.2% · C− 63.1% · C 63.7%**.

| Test (C − B unless stated) | Estimate | 95% CI | Verdict |
| --- | --- | --- | --- |
| Mean daily cost (H) | −69 | [−125, −25] | Exploratory secondary: CI excludes 0 |
| 95th-percentile daily cost (H) | −21 | [−596, +186] | Not significant |
| Total shortfall (H) | −10.1 GWh (−6.7%) | [−24.3, +0.3] | Borderline |
| C vs B+, mean cost (risk-aware rule) | −71 | [−158, −16] | Exploratory: CI excludes 0 |
| C vs C−, mean cost (conditional uncertainty) | −19 | [−47, +13] | Not significant |
| p95 better in future cases | 3 of 4 | every CI includes 0 | Not significant |

The pre-registered criteria H1 and H3 are met on point estimates but are not statistically supported for the tail metric. C leads B in all 8 sensitivity variants; the gap widens with a half-size battery (+4.5 points) and a lower stress threshold (+4.2). The fixed rule nearly fails in future systems (4–7%), because net-demand peaks move with wind and solar. All arms share almost the same worst day: daily-cycling storage cannot cover multi-day deficits.

## 6. Discussion

1. **The headline hypothesis is not supported as stated.** Uncertainty-aware decisions are not demonstrably more robust in the tail with 22 months of data. They are slightly better on average, and the benefit grows as flexibility becomes scarce.
2. **Most value comes from optimisation itself and forecast accuracy.** The forecast-error gap to perfect foresight (36% of value) dwarfs the risk-awareness gain (2.4 points). For a flexibility operator, better forecasts and any optimisation matter more than sophisticated risk models.
3. **Where C's gain comes from:** it comes from the risk-aware decision rule, not from conditional calibrated quantiles; a simple unconditional error distribution does almost as well. Calibration is still valuable for honest communication of uncertainty.
4. **Future stress is energy-limited, not power-limited.** Multi-day cold, still periods are beyond what daily batteries can address. This points towards long-duration storage, demand-side flexibility over several days, and firm low-carbon capacity.

## 7. Limitations

1. The forecaster trails NESO by about 50% on National Demand (six equal-weight weather sites, no solar-generation forecast).
2. The scenario engine uses an idealised EV profile, embedded-wind shapes for offshore wind, and only 2013–2025 weather (no climate change, no 1-in-20 winter).
3. The decision model is a single aggregated battery with no network, prices or degradation, a stylised cost index, and no state of charge carried between days.
4. The future decision setting ignores wind and solar forecast error, which flatters every arm.
5. One test period (22 months); tail statistics have wide confidence intervals. A pre-registered 2026 confirmation run (CS-3) found that the baseline rolling CQR maintained its historical coverage rate on unseen 2026 data (verdict PASS; see §8 and `docs/results/cs3_confirmation.md`).

## 8. Reproducibility

- Every experiment is defined by `configs/*.yaml` and rerun by one command (README).
- Environment pinned by `uv.lock`; 201 automated tests; GitHub Actions on Ubuntu and macOS.
- Raw → processed data rebuild verified identical (298,032 × 46 cells).
- A fresh-clone rerun of every experiment was compared with the recorded results; see `docs/reproducibility_audit.md`.
- **CS-3 confirmation run (2026-11-25):** the baseline rolling CQR (frozen at commit 304b7d8) was applied to the genuinely unseen 2026 data under a pre-registered protocol (`docs/cs3_protocol.md`). **Verdict: PASS** — Coverage_90 89.8% on Jan–Feb (n=59 days; target 85–95%) and 90.9% on the 17 highest-demand days Jan–Oct (target ≥ 80%; 95% bootstrap CI 82.8–95.8%). Jan–Oct overall 89.4% (expected 88–92%). This supports the conclusion that the baseline calibration is not over-fitted to 2022–25 patterns. See `docs/results/cs3_confirmation.md` for the full report.

## 9. Future work

1. Population-weighted multi-site weather and an embedded-solar generation forecast, to close the gap to NESO.
2. Wind and solar forecast uncertainty in the decision experiment.
3. Multi-day optimisation and long-duration storage for the cold-still-week problem.
4. Decision-focused training of the forecaster.
5. Regional and network extension (NESO tRESP pathways, PyPSA).
6. Optimised EV flexibility instead of an idealised profile.

## References

- Gibbs, I. & Candès, E. (2021). Adaptive conformal inference under distribution shift. *NeurIPS 34*.
- Gneiting, T. & Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *JASA* 102(477).
- Hong, T. & Fan, S. (2016). Probabilistic electric load forecasting: a tutorial review. *International Journal of Forecasting* 32(3).
- Ke, G. et al. (2017). LightGBM: a highly efficient gradient boosting decision tree. *NeurIPS 30*.
- Mandi, J. et al. (2024). Decision-focused learning: foundations, state of the art, benchmark and future opportunities. *JAIR* 80.
- NESO (2025). *Future Energy Scenarios 2025: Pathways to Net Zero* and data tables ED1/ES1.
- Rockafellar, R. T. & Uryasev, S. (2000). Optimization of conditional value-at-risk. *Journal of Risk* 2(3).
- Romano, Y., Patterson, E. & Candès, E. (2019). Conformalized quantile regression. *NeurIPS 32*.
- Staffell, I., Brett, D., Brandon, N. & Hawkes, A. (2012). A review of domestic heat pumps. *Energy & Environmental Science* 5, 9291.
- Decision-focused learning for future power system decision-making under uncertainty (2024). arXiv:2401.03680.
- On the added value of probabilistic forecasting for PV + battery scheduling (2023). *Energies*.
