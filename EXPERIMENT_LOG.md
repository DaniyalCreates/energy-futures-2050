# Experiment log

Only real, reproducible runs are recorded here. Each entry gives: run ID, date, git commit, config file, data version, metrics, and notes.

_No experiments yet (first experiments come in Batch 3)._

## Data build v1 (not a model experiment)

2026-11-18 · `pipeline all` (download on Dani's Mac, build in Claude's sandbox) · 298,032 rows, 2009–2025 · quality and sanity results in `docs/data_dictionary.md`.

## EXP-001 · Baselines, validation 2023 · run `20261118-1540-77705fe`

- Config: `configs/baselines.yaml` · data v1 (config e0446e27f33da46a) · target underlying_demand · issue 09:00 local D-1 · monthly expanding-window refits from 2009 · test sealed.
- Command: `uv run python -m energy_futures.experiments.baselines`

| Model | MAE | RMSE | MAPE % | Bias | Daily-peak MAE | Peak timing ±1h % | High-demand MAE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| naive_d7 | 1316 | 1857 | 4.4 | −7 | 1451 | 76.2 | 2613 |
| naive_d2 | 2302 | 3118 | 7.8 | −2 | 2565 | 71.0 | 2565 |
| linear_calendar | 1124 | 1485 | 3.9 | +105 | 1084 | 79.2 | 1945 |
| linear_weather_PW | 1089 | 1426 | 3.9 | +351 | 968 | 79.5 | 1409 |

(MW. PW = perfect-weather, an upper bound. High-demand threshold = 95th percentile of 2022.) Training-window sensitivity and interpretation: `docs/results/baselines_validation.md`.

## EXP-002 · LightGBM point, validation 2023 · run `20261118-1639-61745db`

Training-window choice, MAE (MW): NW 768 / 792 / 824 and PW 597 / 620 / 637 for starts 2009 / 2016 / 2020. **2009 chosen** for both. Config `configs/advanced.yaml`.

## EXP-003 · Quantile LightGBM + rolling CQR, validation 2023

Coverage of the 50/80/90% intervals: raw 36.2 / 63.6 / 77.5 → CQR 53.7 / 82.9 / 92.5. Pinball loss 188 → 182 MW.

## EXP-004 · Test 2024–2025 (unsealed once, protocol from commit 61745db) · run `20261118-1641-61745db`

Comparison window 8 Mar 2024 – 31 Dec 2025, MAE (MW):

| Model | Underlying demand | ND |
| --- | --- | --- |
| naive_d7 | 1281 | 2024 |
| linear_calendar | 1135 | 1738 |
| linear_weather_PW | 1089 | 1565 |
| gbm_NW | 797 | 1386 |
| gbm_PW | 657 | 968 |
| gbm_FW (realistic) | 664 | 995 |
| NESO operational | — | **653** |

FW quantiles + CQR coverage on test, 50/80/90%: 48.8 / 79.6 / 90.5 (raw 34.4 / 61.4 / 75.2). The model is better than NESO on 22.3% of days. Full analysis: `docs/results/forecasting_report.md`.

## EXP-005 · FES scenario grid + stress tests · 19 Nov 2026

`uv run python -m energy_futures.experiments.scenarios` · 312 runs · outputs `outputs/scenarios/` · report `docs/results/scenarios_report.md`.

- Peak increase vs 2024, median over weather years (ours / FES, GW): Holistic 2035 13.9 / 16.0, 2050 57.3 / 61.7; Electric Engagement 2050 69.8 / 85.3; Hydrogen Evolution 2050 67.1 / 64.1; Falling Behind 2050 31.1 / 48.7.
- Peak net demand, median / worst (GW): Holistic 2035 46.0 / 48.7; 2050 77.2 / 82.2.
- Cold, still week (9–15 Dec 2022), Holistic 2050: peak 108.2 GW, peak net 81.6 GW, 10.1 TWh net energy in 7 days.
- Sensitivity, Holistic 2035 median peak: central 60.2, 30% unmanaged EV 71.2, hot-water 0.2 59.4 GW.
- Known artefact: EV valley-filling gives zero EV at peak before ~2040 and flattens whole days after ~2040 (EV at peak 21–27 GW vs FES 8–14 GW).

## EXP-006 · Flexibility decision experiment (6 arms) · 19 Nov 2026 · protocol commit 92fd643

Setting H (8 Mar 2024 – Dec 2025, real forecasts), perfect-foresight value captured: A 37.7%, B 61.3%, B+ 61.2%, C− 63.1%, **C 63.7%**.

C − B: mean daily cost −69 [−125, −25]; p95 −21 [−596, +186]; shortfall −10.1 GWh [−24.3, +0.3]. C − C−: mean −19 [−47, +13].

Setting F (FES futures), C − B p95 negative in 3 of 4 cases; all CIs include 0. C ahead of B on every metric in all 8 historical sensitivity variants.

Report: `docs/results/optimisation_report.md`. Outputs: `outputs/optimisation/`.

## AUDIT-001 · Fresh-clone rerun · 19 Nov 2026

All experiments rerun from a clean clone (36 min). 58/59 compared quantities identical; EXP-001 `linear_weather_PW` 1,088.8 vs 1,089.2 MW on x86 (the Mac reproduces 1,089.21). Data rebuild bit-identical. See `docs/reproducibility_audit.md`.

## CS-3 · 2026 Confirmation Run · 25 Nov 2026 · branch improve/phase-b

**Verdict: PASS**

- Protocol: `docs/cs3_protocol.md` (approved by Dani 2026-11-25)
- Scripts: `download_cs3_data_2026.py` → `generate_cs3_quantiles.run()` → `cs3_confirmation.run()`
- Data: 2026-01-01..2026-10-31 (304 days, 14,592 half-hours)
- Deviation 1: schema bug in Stage 14 processing caught by Stage 17 guard before any demand values seen; fix approved.

| Criterion | Value | n days | 95% CI | Threshold | Outcome |
|-----------|:-----:|:------:|:------:|-----------|---------|
| Co-primary 1: Jan–Feb Coverage_90 | **89.8%** | 59 | — | [85%, 95%] | **PASS** |
| Co-primary 2: high-demand Coverage_90 | **90.9%** | 17 | [82.8%, 95.8%] | ≥ 80% | **PASS** |
| Secondary: Jan–Oct overall Coverage_90 | 89.4% | 304 | — | [88%, 92%] expected | Within range |
| Cold days (descriptive) | 84.7% | 11 | — | — | Descriptive |

Environment: Python 3.12.16, lightgbm 4.7.0, numpy 2.5.5, pandas 3.1.1, macOS-15.7.7-arm64.
Runtime: generate_cs3_quantiles 201 s (4 QS refits); cs3_confirmation 2 s.
Outputs: `outputs/v3_cs3_confirmation/`. Full report: `docs/results/cs3_confirmation.md`.
