# Baseline results: validation year 2023

Run `20261118-1540-77705fe` · dataset built 2026-11-18T15:35:17+00:00 (config e0446e27f33da46a) · target `underlying_demand` (MW) · day-ahead, issued 09:00 UK time on D-1 · monthly expanding-window refits.

High-demand threshold (95th percentile of the 365 days before validation): 41,711 MW.

`linear_weather_PW` uses observed weather at the target time (**perfect-weather**, D-009); it is an upper bound for weather value, not a realistic forecast.

```
                      MAE    RMSE  MAPE_pct   bias  daily_peak_MAE  daily_peak_timing_within_1h_pct  high_demand_MAE
naive_d7           1315.9  1856.8       4.4   -7.2          1450.9                             76.2           2612.7
naive_d2           2301.9  3117.6       7.8   -1.5          2565.1                             71.0           2565.1
linear_calendar    1123.7  1484.6       3.9  105.3          1083.5                             79.2           1945.1
linear_weather_PW  1089.2  1426.1       3.9  351.4           967.5                             79.5           1408.5
```

## Training-window sensitivity (linear models, validation 2023)

| train_start | linear_calendar MAE / bias (MW) | linear_weather_PW MAE / bias (MW) |
| --- | --- | --- |
| 2009 (default) | 1124 / +105 | 1089 / +351 |
| 2016 | 1097 / +73 | 1041 / +244 |
| 2020 | 1093 / +15 | 1020 / +120 |
| 2022 | 1103 / +15 | 998 / +135 |

## Interpretation (validation evidence only; test set still sealed)

1. **The linear models beat the weekly naive** on average: MAE 1,124 MW (calendar) and 1,089 MW (perfect-weather) vs 1,316 MW, i.e. 15–17% lower. The D-2 naive is poor (2,302 MW) because it copies the wrong weekday.
2. **Weather matters most when demand is high:** high-demand MAE falls from 1,945 to 1,409 MW (−28%), but the average MAE only falls 3%. The lags already carry most of the weather information.
3. **A negative result:** in June–August both linear models are worse than `naive_d7`. One global set of coefficients for all seasons and times of day is too rigid. This motivates non-linear models (Batch 4), not more linear terms.
4. **Bias from older data:** with training from 2009, the perfect-weather model over-forecasts by 351 MW on average, because demand levels have fallen. Shorter windows cut the bias and the MAE. The training window is a model-selection choice for Batch 4, made on validation data only.
5. Daily peak timing is within ±1 hour on 76–80% of days for all non-trivial models.

**Not yet established:** any comparison with NESO's own forecast (needs the realistic-weather setting, D-009) and any test-set (2024–2025) performance.

Figures: `docs/figures/baselines_week_jan2023.png`, `baselines_mae_by_hour.png`, `baselines_mae_by_month.png`.
