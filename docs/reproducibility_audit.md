# Reproducibility audit (Step 47)

_19 Nov 2026 · audited commit `daa6fb4` · Claude's x86-64 Linux workspace, plus Dani's Apple Silicon Mac for the data rebuild and the EXP-001 cross-check._

## Summary

From a fresh clone with the locked environment, **every experiment reproduced its recorded results exactly (58 of 59 compared quantities)**. The one difference is 0.4 MW in a single linear-baseline MAE (1,088.8 vs 1,089.2 MW, 0.04%), caused by floating-point differences between processor architectures. The Mac reproduces the recorded value exactly. The raw → processed data rebuild is bit-identical.

## Procedure

1. `git clone` → `uv sync --locked` (54 packages resolved from `uv.lock`) → `uv lock --check` (lockfile consistent).
2. `uv run pytest`: 64 passed, 5 skipped. The 5 dashboard tests skip until outputs exist, by design.
3. Copied in only the inputs that cannot be fetched from the sandbox: `data/processed/` (dataset v1), plus the raw NESO benchmark, archived-forecast and FES files.
4. Ran every experiment command in sequence (2,149 s ≈ 36 min): baselines 9 s · advanced validation 743 s · advanced test 1,187 s · report 1 s · scenarios 112 s · optimisation historical 62 s, future 22 s, report 3 s.
5. Compared the rerun outputs with the recorded outputs (`/tmp/audit_compare.py`; table below).
6. On the Mac, rebuilt `data/processed/demand_weather.parquet` from the raw files with `pipeline build` and compared it cell by cell with the dataset used in all experiments.

## Results

| Experiment | Quantities compared | Identical |
| --- | --- | --- |
| EXP-001 | 4 | 3 |
| EXP-002 | 6 | 6 |
| EXP-003 | 8 | 8 |
| EXP-004 | 16 | 16 |
| EXP-005 | 4 | 4 |
| EXP-006 | 21 | 21 |

- **EXP-001:** the `linear_weather_PW` MAE is 1,088.8 MW on x86-64 against the recorded 1,089.2 MW. A rerun on the Mac (aarch64, where it was originally run) gives 1,089.21, identical to the record. Cause: ordinary least squares on many correlated one-hot and weather columns is numerically sensitive, and OpenBLAS uses different floating-point paths on the two architectures. The other three EXP-001 values match.
- **LightGBM (EXP-002/004):** bit-identical across runs (fixed `random_state`, same data).
- **Bootstrap CIs (EXP-006):** identical (fixed seeds).
- **Data rebuild:** 298,032 × 46, `DataFrame.equals` → True.
- **Dependency audit:** `pip-audit` on all 156 pinned packages found no known vulnerabilities.
- **CI simulation:** a clean clone with no data gives 58 passed, 11 skipped (data-dependent), as GitHub Actions will run.

## Notes

- The raw-data manifest hash changed from `31c6628…` (dataset v1 build) to `e05f6259…` because later downloads (NESO benchmark, archived forecasts, FES) appended rows to the same manifest. The NESO demand and weather rows used to build v1 are unchanged, as the bit-identical rebuild confirms.
- Full reproduction from scratch also needs the downloads (NESO, Open-Meteo), which can only run with normal internet access. They were run on the Mac (D-013) and are not re-tested here.
