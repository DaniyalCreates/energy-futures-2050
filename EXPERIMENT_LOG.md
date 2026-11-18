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
