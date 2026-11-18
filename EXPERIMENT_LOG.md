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
