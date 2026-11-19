# KTP case study: Energy Futures 2050

**Daniyal Tariq · MSc AI & Data Science (University of Hull, 2026) · November 2026**

_An independent applied-AI research project, structured the way a Knowledge Transfer Partnership is: a real business problem, academic methods, a working prototype, honest evaluation and a path to deployment. All figures come from this repository's experiments. Commercial impacts are **hypothetical** unless stated otherwise._

## 1. The business problem

Battery operators, aggregators, suppliers with flexible tariffs and distribution network operators all make the same daily decision: how to schedule flexibility for tomorrow, given uncertain demand. Over-confident schedules waste storage on the wrong hours or, worse, create new peaks. GB peak demand under NESO's FES 2025 pathways rises by tens of GW by 2050, and electric vehicles and heat pumps change when those peaks occur. Getting the decision right under uncertainty becomes more valuable each year.

**Question a company would ask:** "Is it worth investing in probabilistic forecasting and risk-aware optimisation, or is a good point forecast enough?"

## 2. What I built (12-week-style programme, delivered as 8 batches)

| Component | What it does | Evidence |
| --- | --- | --- |
| Data pipeline | Downloads, validates and versions 17 years of NESO demand and weather; stops on any data defect | Rebuild reproduces the dataset exactly (298,032 rows) |
| Day-ahead forecaster | LightGBM with leakage-tested features and archived weather forecasts | 664 MW MAE (2.2%), 48% better than naive; benchmarked honestly against NESO (653 MW on its target) |
| Calibrated uncertainty | Quantile models + rolling conformal calibration | 90% intervals cover 90.5% of out-of-sample outcomes |
| Scenario engine | Turns FES 2025 pathways into half-hourly 2030–2050 demand across 13 weather years | Energy matches FES exactly; peak growth within ~13% of FES for two pathways |
| Decision optimiser | Battery LP, deterministic and CVaR risk-aware, six pre-registered methods | 61–64% of perfect-foresight value vs 38% for a fixed rule |
| Dashboard | Streamlit app labelling every number as observed, forecast or simulated | 5 pages, headless-tested |
| Engineering | `uv`-locked environment, 69 tests, GitHub Actions, decision log, experiment log | Fresh-clone rerun audit |

## 3. What the evidence says (including what didn't work)

- **Optimising beats rules:** forecast-driven scheduling captured 61% of the achievable battery value on real 2024–25 data, against 38% for a typical fixed rule. In future high-renewable systems the fixed rule captured only 4–7%.
- **Uncertainty-awareness helps a little, consistently:** +2.4 percentage points; significant on average cost, **not** significant for worst-day risk. The benefit grows when storage is scarce (+4.5 points with half the battery).
- **Forecast accuracy is the bigger prize:** 36% of value is still lost to forecast error. Our forecaster is about 50% less accurate than NESO's operational one, and I documented why that is likely and how to close the gap.
- **The system-level risk is multi-day:** a cold, still week like December 2022 creates a ~10 TWh energy need in a 2050 system, far beyond daily batteries.

I report these results because the protocol was fixed in advance. Being clear about a weaker-than-hoped result is part of the deliverable.

## 4. Commercial potential (hypothetical, to be validated with a partner)

| Partner type | Possible use | What would need validating |
| --- | --- | --- |
| Battery owner / aggregator | Risk-aware day-ahead scheduling; quantify value lost to forecast error | Real asset data, market prices, degradation |
| Electricity supplier | Demand forecasting with calibrated intervals for hedging and imbalance | Portfolio-level data; settlement-period prices |
| Distribution network operator | Flexibility procurement planning under FES-style growth | Regional data (NESO tRESP), network constraints |
| Local authority / energy planner | Scenario and stress exploration for Local Area Energy Plans | Local demand and asset data |

No savings figures are claimed. The cost index is stylised, and turning it into money requires a partner's prices and contracts.

## 5. Skills demonstrated

- **Business framing:** turned a vague ambition ("AI digital twin for 2050") into a testable decision question with stated success criteria.
- **Applied ML:** time-series feature engineering without leakage, gradient boosting, quantile regression, conformal calibration, proper backtesting.
- **Operational research:** linear programming, CVaR risk measures, constraint modelling (power, energy, efficiency, state of charge).
- **Energy-domain learning:** NESO data definitions, settlement periods, embedded generation, FES pathways, heat-pump and EV load behaviour.
- **Research integrity:** pre-registration, held-out tests used once, bootstrap confidence intervals, published negative results, a documented decision log (39 decisions).
- **Engineering:** reproducible environments, automated tests, CI, version control, data provenance and licensing.
- **Communication:** dashboard for non-specialists, technical report, this case study.

## 6. How this could grow into a university–industry partnership

1. **Months 0–6:** replace the national proxy with the partner's own asset or portfolio data; add prices and degradation; close the forecasting gap (multi-site weather, solar forecast).
2. **Months 6–18:** multi-day and long-duration storage optimisation; wind and solar forecast uncertainty; decision-focused training of the forecaster.
3. **Months 18–30:** regional and network extension (tRESP, PyPSA); a live decision-support tool embedded in the partner's workflow; academic publication of the benchmark.

This is exactly the structure of a KTP: an academic supervisor for the forecasting and optimisation methods, a company supervisor for the operational problem, and an associate who can carry the work from data to deployment.

## 7. Honest boundaries

The project is a prototype. It is not a network model, not a validated digital twin, and not a prediction of 2050. Technical work alone does not guarantee a role or visa sponsorship. Its purpose is to show the method, judgement and delivery a KTP Associate needs.
