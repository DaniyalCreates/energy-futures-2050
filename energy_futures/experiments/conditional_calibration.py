"""
CS-2a: Conditional recalibration method code.

Implements Baseline (reproduces existing rolling CQR), Candidate A (Mondrian CQR),
Candidate B (width-normalised CQR), and Candidate C (Mondrian with extended cold window).

No evaluation is run here — that is CS-2b. This file is committed before any results.
No 2026 data is loaded or accessed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from energy_futures.forecast import task

REPO = Path(__file__).resolve().parents[2]
TZ = "Europe/London"
COLD_THRESHOLD_C = 3.0
MIN_DAYS_STRATUM = 20
DATA_CUTOFF_YEAR = 2025  # hard guard — never load data after this year
CITIES = ["london", "birmingham", "manchester", "newcastle", "glasgow", "cardiff"]

# (lo_col, hi_col, alpha) for each interval name
INTERVALS: dict[str, tuple[str, str, float]] = {
    "90": ("q05", "q95", 0.1),
    "80": ("q10", "q90", 0.2),
    "50": ("q25", "q75", 0.5),
}
Q_COLS = ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]


def _cqr_level(alpha: float, n: int) -> float:
    return min(1.0, (1 - alpha) * (n + 1) / n)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_forecast_temp_daily() -> pd.Series:
    """Archived ~48 h-ahead GB mean temperature; local date index; 2024-25 only."""
    fcast_dir = REPO / "data" / "raw" / "weather_forecast"
    frames = []
    for year in [2024, 2025]:
        city_temps = []
        for city in CITIES:
            path = fcast_dir / f"{city}_{year}.json"
            with open(path) as fh:
                raw = json.load(fh)
            ts = pd.to_datetime(raw["hourly"]["time"]).tz_localize("UTC")
            temp = pd.Series(
                raw["hourly"]["temperature_2m_previous_day2"],
                index=ts,
                dtype=float,
                name=city,
            )
            city_temps.append(temp)
        gb = pd.concat(city_temps, axis=1).mean(axis=1)
        frames.append(gb)
    combined = pd.concat(frames).sort_index().ffill()
    combined.index = combined.index.tz_convert(TZ)
    daily = combined.resample("D").mean()
    daily.index = [d.date() for d in daily.index]
    return daily


def load_development_data() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Load all CS-2 development data with hard 2026 guard.

    Returns
    -------
    raw_q       : DataFrame (UTC indexed) cols q05/q10/q25/q50/q75/q90/q95
    y           : Series (UTC indexed) actual underlying demand
    temp_proxy  : Series (local date index) temperature proxy for each forecast day D:
                  D-2 observed GB mean for 2022-23 (Amendment 1); archived ~48 h-ahead
                  forecast for 2024-25.
    """
    q2223 = pd.read_parquet(
        REPO / "outputs" / "advanced" / "validation" / "quantiles_2022_2023.parquet"
    )
    qfw = pd.read_parquet(
        REPO / "outputs" / "advanced" / "test" / "quantiles_FW_raw.parquet"
    )
    raw_q = pd.concat([q2223, qfw]).sort_index()

    if raw_q.index.tz_convert(TZ).year.max() > DATA_CUTOFF_YEAR:
        raise ValueError(
            f"2026 data guard: raw_q contains dates after {DATA_CUTOFF_YEAR}. "
            "2026 data is reserved for the confirmation run (CS-3)."
        )

    demand = pd.read_parquet(
        REPO / "data" / "processed" / "demand_weather.parquet",
        columns=["underlying_demand", "temperature_2m_gb_mean"],
    )
    y = demand["underlying_demand"].reindex(raw_q.index)

    # Observed daily mean temperature in local time (for D-2 proxy, Amendment 1)
    obs_hh = demand["temperature_2m_gb_mean"].reindex(raw_q.index)
    local_idx = raw_q.index.tz_convert(TZ)
    obs_local = pd.Series(obs_hh.values, index=local_idx)
    obs_daily = obs_local.resample("D").mean()
    obs_by_date = pd.Series(obs_daily.values, index=[d.date() for d in obs_daily.index])
    # D-2 shift: for each forecast day D, temp proxy = observed temp on D-2
    obs_by_date_shifted = obs_by_date.shift(2)

    # Archived forecast temperature (2024-25 only)
    temp_fcast = _load_forecast_temp_daily()

    # Build combined proxy indexed by local date
    all_dates = sorted({d.date() for d in local_idx})
    proxy: dict = {}
    for d in all_dates:
        if d.year <= 2023:
            proxy[d] = obs_by_date_shifted.get(d, np.nan)
        else:
            proxy[d] = temp_fcast.get(d, np.nan)
    temp_proxy = pd.Series(proxy)

    return raw_q, y, temp_proxy


# ---------------------------------------------------------------------------
# Stratification
# ---------------------------------------------------------------------------

def assign_stratum(
    day: object,
    temp_proxy: float,
    max_q50: float,
    threshold_95: float,
) -> str:
    """Assign forecast day D to a stratum using priority order: cold → high_demand → normal.

    Parameters
    ----------
    day         : calendar date of day D (unused in logic; retained for callers)
    temp_proxy  : temperature known at 09:00 D-1 (°C)
    max_q50     : daily maximum q50 for day D
    threshold_95: 95th percentile of daily-max q50 over the current W_t
    """
    if temp_proxy < COLD_THRESHOLD_C:
        return "cold"
    if max_q50 >= threshold_95:
        return "high_demand"
    return "normal"


# ---------------------------------------------------------------------------
# Calibration functions
# ---------------------------------------------------------------------------

def calibrate_baseline(scores_window: np.ndarray, alpha: float = 0.1) -> float:
    """Finite-sample (1-alpha) conformal correction from CQR scores."""
    n = len(scores_window)
    if n == 0:
        return 0.0
    return float(np.quantile(scores_window, _cqr_level(alpha, n)))


def calibrate_mondrian(
    scores_window: np.ndarray,
    strata_window: np.ndarray,
    target_stratum: str,
    min_days: int = MIN_DAYS_STRATUM,
    alpha: float = 0.1,
) -> float:
    """Mondrian CQR correction; falls back to global baseline when stratum is too small.

    Parameters
    ----------
    scores_window   : CQR nonconformity scores per half-hour in W_t
    strata_window   : stratum label per half-hour in W_t (same length as scores_window)
    target_stratum  : stratum to calibrate for
    min_days        : minimum calendar days required in stratum; days approximated as
                      n_halfhours // 48 (error ≤ 2 days per year from clock changes)
    alpha           : miscoverage rate (0.1 → 90% interval)
    """
    mask = strata_window == target_stratum
    s_stratum = scores_window[mask]
    n_days_approx = len(s_stratum) // 48
    if n_days_approx < min_days:
        return calibrate_baseline(scores_window, alpha)
    return calibrate_baseline(s_stratum, alpha)


def calibrate_width_normalised(norm_scores_window: np.ndarray, alpha: float = 0.1) -> float:
    """(1-alpha) correction from width-normalised CQR scores.

    The correction is then applied multiplicatively:
      [q_lo - c*(q_hi - q_lo),  q_hi + c*(q_hi - q_lo)]
    """
    n = len(norm_scores_window)
    if n == 0:
        return 0.0
    return float(np.quantile(norm_scores_window, _cqr_level(alpha, n)))


# ---------------------------------------------------------------------------
# Rolling calibration
# ---------------------------------------------------------------------------

def apply_calibration_daily(
    raw_quantiles: pd.DataFrame,
    actuals: pd.Series,
    temp_series: pd.Series,
    method: str,
    window_days: int = 365,
    apply_from: str | None = None,
) -> pd.DataFrame:
    """Apply daily rolling calibration over all forecast days.

    Parameters
    ----------
    raw_quantiles : DataFrame (UTC indexed) with q05/q10/q25/q50/q75/q90/q95
    actuals       : Series (UTC indexed) actual underlying demand
    temp_series   : Series (local date index, datetime.date keys) temperature proxy for D
    method        : "baseline" | "mondrian" | "mondrian_extended" | "width_normalised"
    window_days   : rolling window length in calendar days
    apply_from    : optional local date string "YYYY-MM-DD"; calibrate only from this date

    Returns
    -------
    DataFrame of calibrated quantiles (same index and columns as raw_quantiles)
    """
    days_local = pd.Series(
        raw_quantiles.index.tz_convert(TZ).normalize().tz_localize(None),
        index=raw_quantiles.index,
    )
    if apply_from is not None:
        apply_ts = pd.Timestamp(apply_from)
        eval_mask = days_local >= apply_ts
        out = raw_quantiles[eval_mask].copy()
    else:
        out = raw_quantiles.copy()

    y = actuals.reindex(raw_quantiles.index)

    # Daily max q50 for strata assignment (over all available history)
    daily_max_q50 = raw_quantiles["q50"].groupby(days_local).max()

    grouped = out.groupby(days_local.reindex(out.index)).groups

    for day, rows in grouped.items():
        day_ts = pd.Timestamp(day, tz=TZ)
        cutoff = task.train_cutoff(day_ts)
        window_start = cutoff - pd.Timedelta(days=window_days)

        in_window = (raw_quantiles.index <= cutoff) & (raw_quantiles.index > window_start)
        y_w = y[in_window]
        q_w = raw_quantiles[in_window]
        days_w = days_local[in_window]

        strata_w: np.ndarray | None = None
        day_stratum: str | None = None
        threshold_95: float = np.nan

        if method in ("mondrian", "mondrian_extended"):
            window_dates = days_w.unique()
            w_max = daily_max_q50.reindex(pd.Index(window_dates)).dropna().values
            threshold_95 = float(np.percentile(w_max, 95)) if len(w_max) else np.nan

            day_to_stratum = {
                d: assign_stratum(
                    day=d.date(),
                    temp_proxy=float(temp_series.get(d.date(), np.nan)),
                    max_q50=float(daily_max_q50.get(d, np.nan)),
                    threshold_95=threshold_95,
                )
                for d in window_dates
            }
            strata_w = np.array([day_to_stratum[d] for d in days_w])

            day_date = day_ts.date()
            day_max = float(raw_quantiles.loc[rows, "q50"].max())
            day_stratum = assign_stratum(
                day=day_date,
                temp_proxy=float(temp_series.get(day_date, np.nan)),
                max_q50=day_max,
                threshold_95=threshold_95,
            )

        for name, (lo, hi, alpha) in INTERVALS.items():
            s_all = np.maximum(q_w[lo].values - y_w.values, y_w.values - q_w[hi].values)
            valid = ~np.isnan(s_all)
            s = s_all[valid]

            if method == "baseline":
                c = calibrate_baseline(s, alpha)

            elif method == "mondrian":
                st = strata_w[valid]
                c = calibrate_mondrian(s, st, day_stratum, MIN_DAYS_STRATUM, alpha)

            elif method == "mondrian_extended":
                if day_stratum == "cold":
                    all_hist = raw_quantiles.index <= cutoff
                    y_ext = y[all_hist]
                    q_ext = raw_quantiles[all_hist]
                    days_ext = days_local[all_hist]
                    s_ext_all = np.maximum(
                        q_ext[lo].values - y_ext.values, y_ext.values - q_ext[hi].values
                    )
                    valid_ext = ~np.isnan(s_ext_all)
                    s_ext = s_ext_all[valid_ext]
                    # Assign strata for extended window using current W_t threshold_95
                    ext_dates = days_ext.unique()
                    ext_day_to_stratum = {
                        d: assign_stratum(
                            day=d.date(),
                            temp_proxy=float(temp_series.get(d.date(), np.nan)),
                            max_q50=float(daily_max_q50.get(d, np.nan)),
                            threshold_95=threshold_95,
                        )
                        for d in ext_dates
                    }
                    st_ext = np.array([ext_day_to_stratum[d] for d in days_ext])
                    st_ext = st_ext[valid_ext]
                    # Fallback scores: global 365-day window (not extended)
                    st_w = strata_w[valid]
                    fallback_c = calibrate_baseline(s, alpha)
                    # Mondrian with extended cold: check days via extended window
                    mask_cold = st_ext == "cold"
                    s_cold = s_ext[mask_cold]
                    n_cold_days = len(s_cold) // 48
                    c = calibrate_baseline(s_cold, alpha) if n_cold_days >= MIN_DAYS_STRATUM else fallback_c
                else:
                    st = strata_w[valid]
                    c = calibrate_mondrian(s, st, day_stratum, MIN_DAYS_STRATUM, alpha)

            elif method == "width_normalised":
                width_w = q_w[hi].values - q_w[lo].values
                width_w_valid = width_w[valid]
                nonzero = width_w_valid > 0
                s_norm = np.where(nonzero, s / width_w_valid, 0.0)
                c_norm = calibrate_width_normalised(s_norm, alpha)
                width_d = raw_quantiles.loc[rows, hi] - raw_quantiles.loc[rows, lo]
                out.loc[rows, lo] = raw_quantiles.loc[rows, lo] - c_norm * width_d
                out.loc[rows, hi] = raw_quantiles.loc[rows, hi] + c_norm * width_d
                continue

            else:
                raise ValueError(f"Unknown method: {method!r}. Expected one of: "
                                 "baseline, mondrian, mondrian_extended, width_normalised")

            out.loc[rows, lo] = raw_quantiles.loc[rows, lo] - c
            out.loc[rows, hi] = raw_quantiles.loc[rows, hi] + c

    # Restore quantile monotonicity after symmetric adjustments
    present = [c for c in Q_COLS if c in out.columns]
    out[present] = np.sort(out[present].to_numpy(), axis=1)
    return out


# ---------------------------------------------------------------------------
# Method selection (§7 of pre-registration)
# ---------------------------------------------------------------------------

def select_method(results_dict: dict) -> str:
    """Apply §7 selection criteria to rolling evaluation results.

    Parameters
    ----------
    results_dict : dict mapping method name → metrics dict with keys:
        coverage_90_all   (%), coverage_90_cold (%), coverage_90_high (%),
        width_90 (MW), winkler (MW).
        Must include a "baseline" entry used as the comparison reference.

    Returns
    -------
    Name of the selected method; "baseline" if no candidate passes all four guards.
    """
    if "baseline" not in results_dict:
        raise ValueError("results_dict must include a 'baseline' entry")

    base = results_dict["baseline"]
    passing: dict[str, dict] = {}

    for name, m in results_dict.items():
        # Rule 1: overall coverage in [87%, 93%]
        if not (87.0 <= m["coverage_90_all"] <= 93.0):
            continue
        # Rule 2: cold coverage ≥ baseline cold + 3 pp
        if m["coverage_90_cold"] < base["coverage_90_cold"] + 3.0:
            continue
        # Rule 3: high-demand coverage ≥ baseline high + 3 pp
        if m["coverage_90_high"] < base["coverage_90_high"] + 3.0:
            continue
        # Rule 4: width ≤ 1.25 × baseline width
        if m["width_90"] > 1.25 * base["width_90"]:
            continue
        passing[name] = m

    if not passing:
        return "baseline"

    # Rule 5: minimise max(|cold − 90|, |high − 90|); tie-break by Winkler
    def _score(m: dict) -> tuple:
        worst = max(abs(m["coverage_90_cold"] - 90.0), abs(m["coverage_90_high"] - 90.0))
        return (worst, m["winkler"])

    return min(passing, key=lambda n: _score(passing[n]))
