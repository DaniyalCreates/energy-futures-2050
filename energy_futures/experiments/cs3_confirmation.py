"""
CS-3 confirmation run: applies baseline rolling CQR to 2026 data.

STATUS: committed BEFORE any 2026 data download.
This script MAY NOT be run until Dani approves the protocol by changing
the status line in docs/cs3_protocol.md to "APPROVED by Dani — [date]"
and committing that change to improve/phase-b.

Protocol: docs/cs3_protocol.md
Frozen method: baseline rolling unconditional CQR, as at commit 304b7d8.
Frozen threshold: 44,411.96 MW (§6).
Evaluation window: 2026-01-01..2026-10-31 (fixed, no extension).

Data paths used (§10):
  2026 quantiles: outputs/v3_cs3_confirmation/inputs/quantiles_FW_raw_mac_2026.parquet
  2026 actuals:   data/processed/demand_weather_2026.parquet
  2026 temp:      data/raw/weather_forecast/{city}_2026.json  (6 cities)

Historical data for calibration lookback (read-only, existing files):
  outputs/advanced/validation/quantiles_2022_2023.parquet
  outputs/v2_cs2_rolling/inputs/quantiles_FW_raw_mac_2024-2025.parquet
  data/processed/demand_weather.parquet

Outputs: outputs/v3_cs3_confirmation/
  cs3_verdict.txt          PASS / FAIL / MIXED / INCONCLUSIVE
  metrics_by_period.csv    per-period coverage
  package_versions.txt     Python, lightgbm, numpy, pandas, platform
"""

from __future__ import annotations

import datetime
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from energy_futures.experiments.conditional_calibration import apply_calibration_daily

TZ = "Europe/London"
CS3_START = datetime.date(2026, 1, 1)
CS3_END = datetime.date(2026, 10, 31)
HIGH_DEMAND_THRESHOLD_MW = 44_411.96  # frozen from CS-2b §6
COLD_THRESHOLD_C = 3.0
CITIES = ["london", "birmingham", "manchester", "newcastle", "glasgow", "cardiff"]

# --- Protocol paths ---
Q2026_PATH = REPO / "outputs" / "v3_cs3_confirmation" / "inputs" / "quantiles_FW_raw_mac_2026.parquet"
DEMAND_2026_PATH = REPO / "data" / "processed" / "demand_weather_2026.parquet"
Q2223_PATH = REPO / "outputs" / "advanced" / "validation" / "quantiles_2022_2023.parquet"
Q2425_PATH = REPO / "outputs" / "v2_cs2_rolling" / "inputs" / "quantiles_FW_raw_mac_2024-2025.parquet"
DEMAND_PATH = REPO / "data" / "processed" / "demand_weather.parquet"
OUT_DIR = REPO / "outputs" / "v3_cs3_confirmation"


# ---------------------------------------------------------------------------
# Date guard
# ---------------------------------------------------------------------------

def _date_guard(raw_q: pd.DataFrame) -> None:
    """Raise ValueError if any 2026 rows fall outside 2026-01-01..2026-10-31."""
    local_dates = raw_q.index.tz_convert(TZ).normalize().tz_localize(None)
    is_2026 = local_dates.year == 2026
    if not is_2026.any():
        return
    dates_2026 = local_dates[is_2026]
    lo = pd.Timestamp("2026-01-01")
    hi = pd.Timestamp("2026-10-31")
    out_of_range = dates_2026[(dates_2026 < lo) | (dates_2026 > hi)]
    if len(out_of_range) > 0:
        raise ValueError(
            f"CS-3 date guard: 2026 rows outside 2026-01-01..2026-10-31 detected "
            f"({out_of_range.min().date()} .. {out_of_range.max().date()}). "
            "Only 2026-01-01..2026-10-31 is permitted (cs3_protocol.md §7)."
        )


# ---------------------------------------------------------------------------
# Temperature proxy loader (2026)
# ---------------------------------------------------------------------------

def _load_forecast_temp_2026() -> pd.Series:
    """Archived ~48 h-ahead GB mean temperature for 2026; local date index.

    Loads per-city JSON files from data/raw/weather_forecast/{city}_2026.json.
    Returns a Series of daily mean temperatures indexed by datetime.date.
    Returns all-NaN Series if any file is not found (data not yet downloaded).
    """
    fcast_dir = REPO / "data" / "raw" / "weather_forecast"
    city_frames = []
    for city in CITIES:
        path = fcast_dir / f"{city}_2026.json"
        if not path.exists():
            raise FileNotFoundError(
                f"CS-3 weather file missing: {path}. "
                "Run download_cs3_data_2026.forecast_weather_2026() first "
                "(requires Dani's protocol approval)."
            )
        with open(path) as fh:
            raw = json.load(fh)
        ts = pd.to_datetime(raw["hourly"]["time"]).tz_localize("UTC")
        temp = pd.Series(
            raw["hourly"]["temperature_2m_previous_day2"],
            index=ts,
            dtype=float,
            name=city,
        )
        city_frames.append(temp)
    gb = pd.concat(city_frames, axis=1).mean(axis=1).sort_index()
    gb.index = gb.index.tz_convert(TZ)
    daily = gb.resample("D").mean()
    result = pd.Series(
        daily.values,
        index=[d.date() for d in daily.index],
        dtype=float,
    )
    result = result[(result.index >= CS3_START) & (result.index <= CS3_END)]
    return result


# ---------------------------------------------------------------------------
# Coverage metric
# ---------------------------------------------------------------------------

def coverage_90(
    cal_q: pd.DataFrame,
    y: pd.Series,
    mask: pd.Index | None = None,
) -> float:
    """Coverage_90: fraction of half-hours where actual ∈ [q05, q95].

    Parameters
    ----------
    cal_q : calibrated quantiles (UTC indexed, must have q05 and q95 columns)
    y     : actual underlying demand (UTC indexed)
    mask  : optional index subset to restrict evaluation

    Returns
    -------
    Coverage as a percentage (0-100), or NaN if no valid rows.
    """
    if mask is not None:
        cal_q = cal_q.reindex(mask)
    y_a = y.reindex(cal_q.index)
    valid = y_a.notna() & cal_q["q05"].notna() & cal_q["q95"].notna()
    if valid.sum() == 0:
        return float("nan")
    inside = (y_a[valid] >= cal_q.loc[valid, "q05"]) & (y_a[valid] <= cal_q.loc[valid, "q95"])
    return float(inside.mean() * 100.0)


# ---------------------------------------------------------------------------
# Block-bootstrap CI for Coverage_90 (co-primary 2)
# ---------------------------------------------------------------------------

def _block_bootstrap_ci_coverage(
    cal_q: pd.DataFrame,
    y: pd.Series,
    hd_dates: set,
    block_size: int = 7,
    n_boot: int = 1_000,
    seed: int = 42,
) -> tuple[float, float]:
    """95% block-bootstrap CI for Coverage_90 on high-demand days (§8 co-primary 2).

    Resamples by day (each block is block_size consecutive high-demand days from the
    sorted list). Returns (lo_pct, hi_pct) = 2.5th and 97.5th percentiles.
    Returns (nan, nan) if hd_dates is empty or no coverage can be computed.
    """
    dates_sorted = sorted(hd_dates)
    n = len(dates_sorted)
    if n == 0:
        return float("nan"), float("nan")

    local_arr = cal_q.index.tz_convert(TZ).normalize().tz_localize(None)
    date_to_iloc: dict[datetime.date, list[int]] = {}
    for i, ts in enumerate(local_arr):
        d = ts.date()
        date_to_iloc.setdefault(d, []).append(i)

    y_arr = y.reindex(cal_q.index).to_numpy()
    q05_arr = cal_q["q05"].to_numpy()
    q95_arr = cal_q["q95"].to_numpy()

    rng = np.random.default_rng(seed)
    n_blocks_avail = max(1, n - block_size + 1)
    boot_coverages: list[float] = []

    for _ in range(n_boot):
        starts = rng.integers(0, n_blocks_avail, size=(n // block_size) + 2)
        idx_flat = np.concatenate(
            [np.arange(s, min(s + block_size, n)) for s in starts]
        )[:n]
        iloc_all: list[int] = []
        for di in idx_flat:
            d = dates_sorted[int(di)]
            if d in date_to_iloc:
                iloc_all.extend(date_to_iloc[d])
        if not iloc_all:
            continue
        ia = np.array(iloc_all)
        valid = ~np.isnan(y_arr[ia]) & ~np.isnan(q05_arr[ia]) & ~np.isnan(q95_arr[ia])
        if valid.sum() == 0:
            continue
        inside = (y_arr[ia][valid] >= q05_arr[ia][valid]) & (
            y_arr[ia][valid] <= q95_arr[ia][valid]
        )
        boot_coverages.append(float(inside.mean() * 100.0))

    if len(boot_coverages) < 2:
        return float("nan"), float("nan")
    return float(np.percentile(boot_coverages, 2.5)), float(np.percentile(boot_coverages, 97.5))


# ---------------------------------------------------------------------------
# §8 criteria computation
# ---------------------------------------------------------------------------

def _make_verdict(
    cov_jan_feb: float,
    cov_hd: float,
    n_hd: int,
    cov_jan_oct: float,
    cov_cold: float,
    n_cold: int,
) -> tuple[str, str]:
    """Apply §8 pass criteria and return (verdict_label, reasons_string).

    Co-primary 1: cov_jan_feb ∈ [85%, 95%]
    Co-primary 2: cov_hd ≥ 80% (requires n_hd ≥ 5; else INCONCLUSIVE)
    """
    if np.isnan(cov_jan_feb):
        return (
            "INCONCLUSIVE",
            "Co-primary 1: insufficient Jan-Feb 2026 data (cov_jan_feb is NaN).",
        )

    pass1 = 85.0 <= cov_jan_feb <= 95.0
    label1 = "PASS" if pass1 else "FAIL"

    if n_hd < 5:
        return (
            f"{label1} (co-primary 1 only; co-primary 2 INCONCLUSIVE)",
            (
                f"Co-primary 1 (Jan-Feb Coverage_90): {cov_jan_feb:.1f}% [85–95%] → {label1}. "
                f"Co-primary 2: n_hd={n_hd} < 5 — INCONCLUSIVE (high-demand). "
                f"Secondary (Jan-Oct Coverage_90): {cov_jan_oct:.1f}% [88–92% expected]. "
                f"Cold days (descriptive, n={n_cold}): {cov_cold:.1f}%."
            ),
        )

    if np.isnan(cov_hd):
        return (
            f"{label1} (co-primary 1 only; co-primary 2 INCONCLUSIVE)",
            (
                f"Co-primary 1 (Jan-Feb Coverage_90): {cov_jan_feb:.1f}% [85–95%] → {label1}. "
                f"Co-primary 2: cov_hd is NaN — INCONCLUSIVE (high-demand). "
                f"Secondary (Jan-Oct Coverage_90): {cov_jan_oct:.1f}% [88–92% expected]. "
                f"Cold days (descriptive, n={n_cold}): {cov_cold:.1f}%."
            ),
        )

    pass2 = cov_hd >= 80.0
    label2 = "PASS" if pass2 else "FAIL"

    if pass1 and pass2:
        verdict = "PASS"
    elif pass1 and not pass2:
        verdict = "MIXED"
    else:
        verdict = "FAIL"

    reasons = (
        f"Co-primary 1 (Jan-Feb Coverage_90): {cov_jan_feb:.1f}% [85–95%] → {label1}. "
        f"Co-primary 2 (high-demand Coverage_90, n={n_hd}): {cov_hd:.1f}% [≥80%] → {label2}. "
        f"Secondary (Jan-Oct Coverage_90): {cov_jan_oct:.1f}% [88–92% expected]. "
        f"Cold days (descriptive, n={n_cold}): {cov_cold:.1f}%."
    )
    return verdict, reasons


def compute_criteria(
    cal_q: pd.DataFrame,
    y: pd.Series,
    temp_proxy: pd.Series,
    raw_q: pd.DataFrame | None = None,
) -> dict:
    """Compute §8 coverage criteria from calibrated quantiles and actuals.

    Parameters
    ----------
    cal_q   : calibrated baseline quantiles (UTC indexed, q05..q95).
              Caller must restrict to 2026-01-01..2026-10-31 before calling.
    y       : actual underlying demand (UTC indexed)
    temp_proxy : local date-indexed temp proxy (datetime.date keys; NaN if unavailable)
    raw_q   : RAW (pre-calibration) quantiles for high-demand day selection (§6).
              If None, falls back to cal_q (use only in tests where raw_q == cal_q).

    Returns
    -------
    dict with coverage values, n_days counts, bootstrap CI for co-primary 2,
    verdict, and reason string.
    """
    local_dates = pd.Series(
        cal_q.index.tz_convert(TZ).normalize().tz_localize(None), index=cal_q.index
    )

    # §8.1 Co-primary 1: Jan-Feb 2026
    jf_lo = pd.Timestamp("2026-01-01")
    jf_hi = pd.Timestamp("2026-02-28")
    mask_jan_feb = cal_q.index[(local_dates >= jf_lo) & (local_dates <= jf_hi)]
    n_days_jan_feb = int(local_dates[mask_jan_feb].nunique())

    # §8.2 Co-primary 2: high-demand days, full Jan-Oct window
    # Protocol §6: select using RAW q50 (pre-calibration), not calibrated q50
    _q_for_hd = raw_q if raw_q is not None else cal_q
    daily_max_q50 = _q_for_hd["q50"].groupby(local_dates).max()
    hd_dates: set[datetime.date] = {
        d.date()
        for d, v in daily_max_q50.items()
        if v >= HIGH_DEMAND_THRESHOLD_MW
    }
    mask_hd = cal_q.index[local_dates.map(lambda ts: ts.date()).isin(hd_dates)]

    # §8.3 Secondary: overall Jan-Oct (all of cal_q — caller already restricted it)
    mask_jan_oct = cal_q.index
    n_days_jan_oct = int(local_dates.nunique())

    # §8.4 Cold days: descriptive
    cold_dates: set[datetime.date] = {
        d
        for d, v in temp_proxy.items()
        if isinstance(d, datetime.date) and np.isfinite(float(v)) and float(v) < COLD_THRESHOLD_C
    }
    mask_cold = cal_q.index[local_dates.map(lambda ts: ts.date()).isin(cold_dates)]

    cov_jan_feb = coverage_90(cal_q, y, mask_jan_feb)
    cov_hd = coverage_90(cal_q, y, mask_hd)
    cov_jan_oct = coverage_90(cal_q, y, mask_jan_oct)
    cov_cold = coverage_90(cal_q, y, mask_cold) if len(mask_cold) else float("nan")

    n_hd = len(hd_dates)
    n_cold = len(cold_dates)

    # 95% block-bootstrap CI for co-primary 2 (by day, 1,000 resamples, seed 42)
    ci_hd_lo, ci_hd_hi = _block_bootstrap_ci_coverage(
        cal_q, y, hd_dates, block_size=7, n_boot=1_000, seed=42
    )

    verdict, reasons = _make_verdict(cov_jan_feb, cov_hd, n_hd, cov_jan_oct, cov_cold, n_cold)

    return {
        "coverage_90_jan_feb": round(cov_jan_feb, 2) if np.isfinite(cov_jan_feb) else float("nan"),
        "n_days_jan_feb": n_days_jan_feb,
        "coverage_90_jan_oct": round(cov_jan_oct, 2) if np.isfinite(cov_jan_oct) else float("nan"),
        "n_days_jan_oct": n_days_jan_oct,
        "coverage_90_high_demand": round(cov_hd, 2) if np.isfinite(cov_hd) else float("nan"),
        "n_high_demand_days": n_hd,
        "ci_high_demand_lo": round(ci_hd_lo, 2) if np.isfinite(ci_hd_lo) else float("nan"),
        "ci_high_demand_hi": round(ci_hd_hi, 2) if np.isfinite(ci_hd_hi) else float("nan"),
        "coverage_90_cold": round(cov_cold, 2) if np.isfinite(cov_cold) else float("nan"),
        "n_cold_days": n_cold,
        "verdict": verdict,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Full run (not to be called until protocol is approved)
# ---------------------------------------------------------------------------

def run(
    q2026_path: Path = Q2026_PATH,
    demand_2026_path: Path = DEMAND_2026_PATH,
    out_dir: Path = OUT_DIR,
) -> dict:
    """Execute the CS-3 confirmation run.

    MUST NOT be called until Dani approves docs/cs3_protocol.md by changing
    the status line to "APPROVED by Dani — [date]" and committing.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Load historical data (calibration lookback; read-only existing files) ---
    q2223 = pd.read_parquet(Q2223_PATH)
    q2425 = pd.read_parquet(Q2425_PATH)
    demand_hist = pd.read_parquet(
        DEMAND_PATH, columns=["underlying_demand", "temperature_2m_gb_mean"]
    )

    # --- Load 2026 quantiles and apply date guard ---
    q2026 = pd.read_parquet(q2026_path)
    _date_guard(q2026)

    # --- Load 2026 actuals and apply date guard ---
    demand_2026 = pd.read_parquet(
        demand_2026_path, columns=["underlying_demand"]
    )
    _date_guard(demand_2026)  # guard on demand file (§7)
    y_2026 = demand_2026["underlying_demand"]

    # --- Combine quantiles and actuals ---
    raw_q = pd.concat([q2223, q2425, q2026]).sort_index()
    y_all = pd.concat([demand_hist["underlying_demand"], y_2026]).sort_index()
    y_all = y_all[~y_all.index.duplicated(keep="last")]

    # --- Temperature proxy for 2026 ---
    temp_2026 = _load_forecast_temp_2026()
    # Merge with historical proxy stub (baseline calibration does not use temp for strata;
    # temp_proxy is only used for cold-day descriptive reporting)
    all_local_dates = sorted(
        {d.date() for d in raw_q.index.tz_convert(TZ)}
    )
    temp_proxy = pd.Series(
        {d: float(temp_2026.get(d, np.nan)) for d in all_local_dates}
    )

    # --- Apply baseline calibration (method frozen at 304b7d8) ---
    cal_q_full = apply_calibration_daily(
        raw_q, y_all, temp_proxy, method="baseline", window_days=365, apply_from="2026-01-01"
    )

    # --- Restrict to evaluation window ---
    local_cal = pd.Series(
        cal_q_full.index.tz_convert(TZ).normalize().tz_localize(None),
        index=cal_q_full.index,
    )
    cal_q = cal_q_full[
        (local_cal >= pd.Timestamp(str(CS3_START)))
        & (local_cal <= pd.Timestamp(str(CS3_END)))
    ]
    y_eval = y_all.reindex(cal_q.index)
    temp_eval = pd.Series(
        {d: temp_proxy.get(d, np.nan) for d in temp_proxy.index if CS3_START <= d <= CS3_END}
    )

    # --- Compute §8 criteria ---
    # Pass raw q2026 so high-demand day selection uses RAW q50 (protocol §6)
    q2026_local = q2026.copy()
    local_q2026 = pd.Series(
        q2026_local.index.tz_convert(TZ).normalize().tz_localize(None),
        index=q2026_local.index,
    )
    raw_q_eval = q2026_local[
        (local_q2026 >= pd.Timestamp(str(CS3_START)))
        & (local_q2026 <= pd.Timestamp(str(CS3_END)))
    ]
    result = compute_criteria(cal_q, y_eval, temp_eval, raw_q=raw_q_eval)

    # --- Write outputs ---
    _write_outputs(result, out_dir)
    print(f"\nCS-3 verdict: {result['verdict']}")
    print(result["reasons"])
    return result


def _write_outputs(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    nan = float("nan")
    metrics_rows = [
        {
            "period": "Jan-Feb 2026 (co-primary 1)",
            "coverage_90_pct": result["coverage_90_jan_feb"],
            "n_days": result["n_days_jan_feb"],
            "ci_lo_pct": nan,
            "ci_hi_pct": nan,
        },
        {
            "period": "Jan-Oct 2026 (co-primary 2: high-demand)",
            "coverage_90_pct": result["coverage_90_high_demand"],
            "n_days": result["n_high_demand_days"],
            "ci_lo_pct": result["ci_high_demand_lo"],
            "ci_hi_pct": result["ci_high_demand_hi"],
        },
        {
            "period": "Jan-Oct 2026 (secondary: overall)",
            "coverage_90_pct": result["coverage_90_jan_oct"],
            "n_days": result["n_days_jan_oct"],
            "ci_lo_pct": nan,
            "ci_hi_pct": nan,
        },
        {
            "period": "Jan-Oct 2026 (cold, descriptive)",
            "coverage_90_pct": result["coverage_90_cold"],
            "n_days": result["n_cold_days"],
            "ci_lo_pct": nan,
            "ci_hi_pct": nan,
        },
    ]
    pd.DataFrame(metrics_rows).to_csv(out_dir / "metrics_by_period.csv", index=False)

    ci_lo = result["ci_high_demand_lo"]
    ci_hi = result["ci_high_demand_hi"]
    ci_str = (
        f"[{ci_lo:.1f}%, {ci_hi:.1f}%]"
        if np.isfinite(ci_lo) and np.isfinite(ci_hi)
        else "n/a (no high-demand days or insufficient data)"
    )
    full_metrics = {
        k: v for k, v in result.items() if k not in ("verdict", "reasons")
    }
    verdict_txt = (
        f"CS-3 VERDICT: {result['verdict']}\n\n"
        f"{result['reasons']}\n\n"
        f"Co-primary 2 (high-demand) 95% bootstrap CI: {ci_str} "
        f"(n_days={result['n_high_demand_days']}, block_size=7, n_boot=1000, seed=42)\n\n"
        f"n_days by period:\n"
        f"  Jan-Feb:          {result['n_days_jan_feb']}\n"
        f"  Jan-Oct overall:  {result['n_days_jan_oct']}\n"
        f"  High-demand:      {result['n_high_demand_days']}\n"
        f"  Cold (descrip.):  {result['n_cold_days']}\n\n"
        f"Full metrics:\n{json.dumps(full_metrics, indent=2)}\n\n"
        f"Protocol: docs/cs3_protocol.md\n"
        f"Frozen threshold: {HIGH_DEMAND_THRESHOLD_MW} MW\n"
        f"Evaluation window: {CS3_START} .. {CS3_END}\n"
    )
    (out_dir / "cs3_verdict.txt").write_text(verdict_txt, encoding="utf-8")

    import lightgbm as lgb

    versions_txt = (
        f"Python: {sys.version}\n"
        f"lightgbm: {lgb.__version__}\n"
        f"numpy: {np.__version__}\n"
        f"pandas: {pd.__version__}\n"
        f"platform: {platform.platform()}\n"
    )
    (out_dir / "package_versions.txt").write_text(versions_txt, encoding="utf-8")


if __name__ == "__main__":
    run()
