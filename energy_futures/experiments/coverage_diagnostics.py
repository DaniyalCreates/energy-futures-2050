"""
CS-1: Coverage diagnostic report for calibrated prediction intervals.

Measures how often the 50 / 80 / 90 % CQR prediction intervals contain
the actual underlying demand, broken down by operating condition.

Diagnostic only — no new modelling methods, no 2026 data.
Outputs go to outputs/v2_cs1_coverage/ (new folder, nothing overwritten).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from energy_futures.features.calendar import calendar_features  # noqa: E402

OUT_DIR = REPO / "outputs" / "v2_cs1_coverage"
REPORT_PATH = REPO / "docs" / "results" / "coverage_diagnostics.md"

QUANTILE_PATHS = {
    "2023": REPO / "outputs" / "advanced" / "validation" / "quantiles_2023_cqr.parquet",
    "2024-25": REPO / "outputs" / "advanced" / "test" / "quantiles_FW_cqr.parquet",
}
DEMAND_PATH = REPO / "data" / "processed" / "demand_weather.parquet"
FCAST_DIR = REPO / "data" / "raw" / "weather_forecast"

# Intervals: (lower quantile column, upper quantile column)
INTERVALS: dict[str, tuple[str, str]] = {
    "50%": ("q25", "q75"),
    "80%": ("q10", "q90"),
    "90%": ("q05", "q95"),
}
COLD_THRESHOLD_C = 3.0
N_BOOT = 1000
RNG_SEED = 42
TZ = "Europe/London"
CITIES = ["london", "birmingham", "manchester", "newcastle", "glasgow", "cardiff"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_forecast_temp_daily() -> pd.Series:
    """Load archived ~48 h-ahead temperatures; return daily GB mean.

    Open-Meteo uses UTC (utc_offset_seconds=0). Daily means are computed on
    UK local time so that e.g. 25 Dec in the JSON = 25 Dec in London.
    Returns a pd.Series with datetime.date index and °C float values.
    Available for 2024-2025 only.
    """
    frames = []
    for year in [2024, 2025]:
        city_temps = []
        for city in CITIES:
            path = FCAST_DIR / f"{city}_{year}.json"
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

    combined = pd.concat(frames).sort_index()
    # Forward-fill any NaN at the edges (possible at year boundaries)
    combined = combined.ffill()
    # Convert to UK local time for calendar-day aggregation
    combined.index = combined.index.tz_convert(TZ)
    daily = combined.resample("D").mean()
    # Store as plain date objects for easy mapping later
    daily.index = [d.date() for d in daily.index]
    return daily


def build_period_df(
    period_key: str,
    demand: pd.DataFrame,
    fcast_temp: pd.Series,
) -> pd.DataFrame:
    """Load quantiles for one period and merge with actual demand + condition flags.

    Parameters
    ----------
    period_key : "2023" or "2024-25"
    demand     : full demand_weather.parquet (UTC half-hourly)
    fcast_temp : daily GB mean forecast temperature (date index; 2024-25 only)
    """
    q = pd.read_parquet(QUANTILE_PATHS[period_key])
    df = q.join(demand[["underlying_demand", "temperature_2m_gb_mean"]], how="inner")
    if len(df) == 0:
        raise ValueError(f"No rows after join for period {period_key!r}")

    # Calendar features (UK local time, via existing calendar module)
    cal = calendar_features(df.index)
    df = df.assign(
        slot=cal["slot"].values,
        month=cal["month"].values,
        is_holiday=cal["is_holiday"].astype(bool).values,
        is_xmas=cal["is_xmas_period"].astype(bool).values,
    )

    # UK local date and year for day-level grouping
    local = df.index.tz_convert(TZ)
    df["date"] = local.date
    df["year"] = local.year

    # Cold: observed temperature (available for both periods)
    daily_obs_temp = df.groupby("date")["temperature_2m_gb_mean"].mean()
    df["cold_obs"] = df["date"].map(daily_obs_temp).values < COLD_THRESHOLD_C

    # Cold: forecast temperature (2024-25 only; not available for 2023)
    if period_key == "2024-25":
        mapped = pd.to_numeric(
            pd.Series(df["date"].map(fcast_temp).values, index=df.index),
            errors="coerce",
        )
        df["cold_fcast"] = mapped < COLD_THRESHOLD_C
    else:
        df["cold_fcast"] = np.nan  # explicitly not available for 2023

    df["is_winter"] = df["month"].isin([12, 1, 2])

    # High-demand days: top 5% by daily maximum underlying demand within this period
    daily_max = df.groupby("date")["underlying_demand"].max()
    threshold_95 = daily_max.quantile(0.95)
    df["is_high_demand"] = df["date"].isin(daily_max[daily_max >= threshold_95].index)

    # Coverage flag and width for each interval
    for label, (lo, hi) in INTERVALS.items():
        df[f"covered_{label}"] = (df["underlying_demand"] >= df[lo]) & (
            df["underlying_demand"] <= df[hi]
        )
        df[f"width_{label}"] = df[hi] - df[lo]

    df["period"] = period_key
    return df


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def bootstrap_coverage(
    day_means: np.ndarray,
    n_boot: int = N_BOOT,
    rng: np.random.Generator | None = None,
) -> tuple[float, float, float]:
    """Block-bootstrap a coverage rate from per-day mean values.

    Resamples whole days (blocks) so that within-day correlations are
    preserved. Returns (mean, ci_low_95, ci_high_95) as fractions (0–1).
    """
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)
    n = len(day_means)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    boot = np.array(
        [rng.choice(day_means, size=n, replace=True).mean() for _ in range(n_boot)]
    )
    return (
        float(day_means.mean()),
        float(np.percentile(boot, 2.5)),
        float(np.percentile(boot, 97.5)),
    )


# ---------------------------------------------------------------------------
# Single-group statistics
# ---------------------------------------------------------------------------

def stats_row(
    sub: pd.DataFrame,
    interval_label: str,
    rng: np.random.Generator,
) -> dict:
    """Coverage and width statistics for a sub-DataFrame and one interval."""
    cov_col = f"covered_{interval_label}"
    wid_col = f"width_{interval_label}"

    day_cov = sub.groupby("date")[cov_col].mean().values
    mean, ci_lo, ci_hi = bootstrap_coverage(day_cov, rng=rng)

    def _r(x: float, nd: int = 2) -> float:
        return round(float(x), nd) if np.isfinite(x) else float("nan")

    return {
        "coverage_pct": _r(mean * 100),
        "ci_low_pct": _r(ci_lo * 100),
        "ci_high_pct": _r(ci_hi * 100),
        "width_mean_mw": _r(sub[wid_col].mean(), 1),
        "n_days": int(sub["date"].nunique()),
        "n_halfhours": int(len(sub)),
    }


# ---------------------------------------------------------------------------
# Aggregation tables
# ---------------------------------------------------------------------------

def compute_condition_table(
    df: pd.DataFrame, rng: np.random.Generator
) -> pd.DataFrame:
    """Return a coverage table for all named binary conditions."""
    period = df["period"].iloc[0]

    conditions: list[tuple[str, pd.Series]] = [
        ("All", pd.Series(True, index=df.index)),
        ("Cold (obs < 3 C)", df["cold_obs"].astype(bool)),
        ("Warm (obs >= 3 C)", ~df["cold_obs"].astype(bool)),
        ("Winter (Dec-Feb)", df["is_winter"]),
        ("Non-winter", ~df["is_winter"]),
        ("Bank holiday", df["is_holiday"]),
        ("Christmas period (24 Dec - 2 Jan)", df["is_xmas"]),
        ("Top-5% demand days", df["is_high_demand"]),
    ]
    if period == "2024-25":
        valid = df["cold_fcast"].notna()
        conditions += [
            ("Cold (fcast < 3 C)", valid & df["cold_fcast"].astype(bool)),
            ("Warm (fcast >= 3 C)", valid & ~df["cold_fcast"].astype(bool)),
        ]

    rows = []
    for cond_name, mask in conditions:
        sub = df[mask]
        if len(sub) == 0:
            continue
        for interval_label in INTERVALS:
            row = {"period": period, "condition": cond_name, "interval": interval_label}
            row.update(stats_row(sub, interval_label, rng))
            rows.append(row)
    return pd.DataFrame(rows)


def compute_group_table(
    df: pd.DataFrame, group_col: str, rng: np.random.Generator
) -> pd.DataFrame:
    """Return a coverage table broken down by a grouping column (month/year/slot)."""
    rows = []
    for grp_val, sub in df.groupby(group_col):
        for interval_label in INTERVALS:
            row = {
                "period": df["period"].iloc[0],
                group_col: grp_val,
                "interval": interval_label,
            }
            row.update(stats_row(sub, interval_label, rng))
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _md_table(df: pd.DataFrame, headers: list[str]) -> str:
    """Format a DataFrame as a GitHub-flavoured markdown pipe table."""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for _, row in df.iterrows():
        cells = []
        for v in row:
            if isinstance(v, float) and not np.isfinite(v):
                cells.append("—")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def generate_report(
    cond_df: pd.DataFrame,
    month_df: pd.DataFrame,
    year_df: pd.DataFrame,
    hour_df: pd.DataFrame,
) -> str:
    """Build the full markdown report and return it as a string."""
    secs = []

    secs.append(
        "# CS-1: Coverage diagnostic for calibrated prediction intervals\n\n"
        "_Generated by `energy_futures/experiments/coverage_diagnostics.py`_  \n"
        "_No new modelling methods · No 2026 data · "
        "Pre-registration seal: laptop only (timing cannot be independently verified)_"
    )

    secs.append(
        "## 1. What this report measures\n\n"
        "For each prediction interval (50%, 80%, 90%), the **empirical coverage** is "
        "the fraction of half-hours in which the actual underlying demand fell inside "
        "the interval. A well-calibrated interval should have coverage close to its "
        "nominal level.\n\n"
        "Confidence intervals (95%) use a **block bootstrap by calendar day** "
        "(1,000 resamples, seed 42). "
        "Half-hours within a day are always resampled together because "
        "forecast errors are strongly correlated within a day.\n\n"
        "**Periods:**\n"
        "- 2023: validation period (monthly expanding-window refits from 2009).\n"
        "- 2024-25: test period (8 Mar 2024 – 31 Dec 2025, one-shot unsealing per D-023).\n\n"
        "**Cold-day definition:**\n"
        "- Both periods: 'cold' = daily GB mean *observed* temperature < 3 °C.\n"
        "- 2024-25 only: 'cold' also computed from the archived ~48 h-ahead "
        "forecast temperature (`previous_day2`, as the operator would have known it). "
        "For 2023, only observed temperature is available; "
        "this is labelled clearly throughout."
    )

    # Overall table
    overall = cond_df[cond_df["condition"] == "All"][
        ["period", "interval", "coverage_pct", "ci_low_pct", "ci_high_pct", "width_mean_mw", "n_days"]
    ].copy()
    secs.append(
        "## 2. Overall coverage\n\n"
        "Nominal targets: 50% → 50.0%, 80% → 80.0%, 90% → 90.0%.\n\n"
        + _md_table(
            overall,
            ["Period", "Interval", "Coverage %", "CI low %", "CI high %", "Avg width (MW)", "Days"],
        )
    )

    # Condition tables
    cond_parts = []
    for period in ["2023", "2024-25"]:
        note = " (observed temperature only — no forecast temperature archived for 2023)" if period == "2023" else ""
        sub = cond_df[cond_df["period"] == period][
            ["condition", "interval", "coverage_pct", "ci_low_pct", "ci_high_pct", "width_mean_mw", "n_days"]
        ]
        cond_parts.append(
            f"### {period}{note}\n\n"
            + _md_table(
                sub,
                ["Condition", "Interval", "Coverage %", "CI low %", "CI high %", "Avg width (MW)", "Days"],
            )
        )
    secs.append("## 3. Coverage by condition\n\n" + "\n\n".join(cond_parts))

    # Year table
    year_tbl = year_df[
        ["period", "year", "interval", "coverage_pct", "ci_low_pct", "ci_high_pct", "width_mean_mw", "n_days"]
    ]
    secs.append(
        "## 4. Coverage by year\n\n"
        "_Note: year 2024 covers only 8 Mar – 31 Dec 2024 (start of forecast-radiation archive)._\n\n"
        + _md_table(
            year_tbl,
            ["Period", "Year", "Interval", "Coverage %", "CI low %", "CI high %", "Avg width (MW)", "Days"],
        )
    )

    # Month table
    month_tbl = month_df[
        ["period", "month", "interval", "coverage_pct", "ci_low_pct", "ci_high_pct", "width_mean_mw"]
    ]
    secs.append(
        "## 5. Coverage by month\n\n"
        + _md_table(
            month_tbl,
            ["Period", "Month", "Interval", "Coverage %", "CI low %", "CI high %", "Avg width (MW)"],
        )
    )

    # Hour table (slot 0–47 = 00:00–23:30 UK local)
    hour_tbl = hour_df[
        ["period", "slot", "interval", "coverage_pct", "ci_low_pct", "ci_high_pct", "width_mean_mw"]
    ]
    secs.append(
        "## 6. Coverage by time of day\n\n"
        "_Slot 0 = 00:00–00:30 UK local time; slot 47 = 23:30–00:00._\n\n"
        + _md_table(
            hour_tbl,
            ["Period", "Slot", "Interval", "Coverage %", "CI low %", "CI high %", "Avg width (MW)"],
        )
    )

    secs.append(
        "## 7. Remaining uncertainty\n\n"
        "- Cold-day classification uses a GB mean temperature across six equal-weight sites "
        "(D-012); population weighting is deferred.\n"
        "- Bank holidays follow England & Wales rules; "
        "Scottish differences are a known simplification (D-021).\n"
        "- Christmas period: 24 Dec – 2 Jan (from `calendar.py`).\n"
        "- 'Top-5% demand days' threshold is computed within each evaluation period separately, "
        "not from a fixed training window.\n"
        "- The 2024-25 test period starts 2024-03-08 (forecast radiation archive); "
        "year 2024 therefore covers March–December only.\n"
        "- Bootstrap CIs assume independent blocks (days). "
        "Demand is seasonally correlated across days, "
        "so CIs may be slightly narrower than a fully block-aware method would give.\n"
        "- No 2026 data was accessed in this analysis."
    )

    secs.append(
        "## 8. Output files\n\n"
        "| File | Description |\n"
        "| --- | --- |\n"
        "| `outputs/v2_cs1_coverage/coverage_conditions.csv` | Binary condition breakdown |\n"
        "| `outputs/v2_cs1_coverage/coverage_by_month.csv` | Monthly breakdown |\n"
        "| `outputs/v2_cs1_coverage/coverage_by_year.csv` | Yearly breakdown |\n"
        "| `outputs/v2_cs1_coverage/coverage_by_hour.csv` | Time-of-day breakdown (slots 0–47) |"
    )

    return "\n\n".join(secs) + "\n"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run CS-1 diagnostics and write all outputs. Returns the four result DataFrames."""
    print("CS-1: Coverage diagnostic — loading data ...")
    demand = pd.read_parquet(DEMAND_PATH)
    fcast_temp = load_forecast_temp_daily()

    cond_parts: list[pd.DataFrame] = []
    month_parts: list[pd.DataFrame] = []
    year_parts: list[pd.DataFrame] = []
    hour_parts: list[pd.DataFrame] = []

    rng = np.random.default_rng(RNG_SEED)

    for period_key in ["2023", "2024-25"]:
        print(f"  Period {period_key}: building data ...")
        df = build_period_df(period_key, demand, fcast_temp)
        print(f"    {len(df):,} half-hours, {df['date'].nunique()} days")
        cond_parts.append(compute_condition_table(df, rng))
        month_parts.append(compute_group_table(df, "month", rng))
        year_parts.append(compute_group_table(df, "year", rng))
        hour_parts.append(compute_group_table(df, "slot", rng))
        print(f"    Done.")

    cond_df = pd.concat(cond_parts, ignore_index=True)
    month_df = pd.concat(month_parts, ignore_index=True)
    year_df = pd.concat(year_parts, ignore_index=True)
    hour_df = pd.concat(hour_parts, ignore_index=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cond_df.to_csv(OUT_DIR / "coverage_conditions.csv", index=False)
    month_df.to_csv(OUT_DIR / "coverage_by_month.csv", index=False)
    year_df.to_csv(OUT_DIR / "coverage_by_year.csv", index=False)
    hour_df.to_csv(OUT_DIR / "coverage_by_hour.csv", index=False)
    print(f"  Results saved to {OUT_DIR}/")

    report = generate_report(cond_df, month_df, year_df, hour_df)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"  Report written to {REPORT_PATH}")

    return cond_df, month_df, year_df, hour_df


if __name__ == "__main__":
    cond_df, _, year_df, _ = run()
    print("\nOverall coverage (All half-hours):")
    overall = cond_df[cond_df["condition"] == "All"][
        ["period", "interval", "coverage_pct", "ci_low_pct", "ci_high_pct", "width_mean_mw"]
    ]
    print(overall.to_string(index=False))
