"""Stress-window search over historical weather (Step 35). Windows are chosen from observed
weather only (temperature, embedded wind and solar capacity factors), never from model outputs."""
import pandas as pd

TZ = "Europe/London"


def daily_weather(d: pd.DataFrame) -> pd.DataFrame:
    local = d.index.tz_convert(TZ).tz_localize(None).normalize()
    wind_cf = (d.embedded_wind_generation / d.embedded_wind_capacity.where(d.embedded_wind_capacity > 0)).clip(0, 1)
    solar_cf = (d.embedded_solar_generation / d.embedded_solar_capacity.where(d.embedded_solar_capacity > 0)).clip(0, 1)
    return pd.DataFrame({"temp": d.temperature_2m_gb_mean, "wind_cf": wind_cf, "solar_cf": solar_cf}).groupby(local).mean()


def cold_still_window(daily: pd.DataFrame, days: int, years: list[int]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Window minimising standardised temperature + standardised wind CF (cold AND still)."""
    dd = daily[daily.index.year.isin(years)]
    z = (dd.temp - dd.temp.mean()) / dd.temp.std() + (dd.wind_cf - dd.wind_cf.mean()) / dd.wind_cf.std()
    end = z.rolling(days).mean().idxmin()
    return end - pd.Timedelta(days=days - 1), end


def low_renewable_window(daily: pd.DataFrame, days: int, years: list[int], wind_twh: float, solar_twh: float):
    """Window with the lowest combined wind+solar output for a given annual energy mix (weights =
    each technology's annual energy / its mean CF), i.e. lowest renewable output in MW terms."""
    dd = daily[daily.index.year.isin(years)]
    out = wind_twh * dd.wind_cf / dd.wind_cf.mean() + solar_twh * dd.solar_cf / dd.solar_cf.mean()
    end = out.rolling(days).mean().idxmin()
    return end - pd.Timedelta(days=days - 1), end


def window_metrics(x: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    local = x.index.tz_convert(TZ).tz_localize(None).normalize()
    w = x[(local >= start) & (local <= end)]
    return {
        "window": f"{start.date()} to {end.date()}",
        "mean_temp_c": float(w.temp.mean()),
        "peak_demand_gw": float(w.demand.max() / 1e3),
        "peak_net_gw": float(w.net.max() / 1e3),
        "mean_net_gw": float(w.net.mean() / 1e3),
        "net_positive_energy_twh": float(w.net.clip(lower=0).sum() / 2 / 1e6),   # energy firm plant/storage/imports must supply
        "vre_share_pct": float((w.wind.sum() + w.solar.sum()) / w.demand.sum() * 100),
    }
