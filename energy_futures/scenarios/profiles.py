"""Half-hourly shapes for new demand and variable generation (Step 34). Each shape sums to 1 over
its year, so multiplying by an annual energy (MWh) and by 2 (MWh per half-hour -> MW) preserves
FES annual energy exactly."""
import numpy as np
import pandas as pd

TZ = "Europe/London"


def normalise(s: pd.Series) -> pd.Series:
    s = s.clip(lower=0).fillna(0)
    tot = s.sum()
    if tot <= 0:
        raise ValueError("shape has no positive mass")
    return s / tot


def staffell_ashp_cop(outdoor_c: pd.Series, flow_c: float) -> pd.Series:
    """Air-source heat pump COP regression from Staffell et al. (2012), Energy Environ. Sci. 5, 9291."""
    dT = (flow_c - outdoor_c).clip(lower=15)          # the regression is fitted for dT of roughly 15-60 K
    return 6.08 - 0.09 * dT + 0.0005 * dT ** 2


def heat_pump_shape(temp_c: pd.Series, base_c: float, flow_c: float, hot_water_share: float) -> pd.Series:
    """Electricity use proportional to heat demand (degree-hours) divided by COP, plus an optional flat
    hot-water share. Flat within the day (heat pumps run steadily): a documented simplification."""
    heat = (base_c - temp_c).clip(lower=0)
    space = normalise(heat / staffell_ashp_cop(temp_c, flow_c))
    flat = normalise(pd.Series(1.0, index=temp_c.index))
    return (1 - hot_water_share) * space + hot_water_share * flat


def window_shape(index: pd.DatetimeIndex, start_h: int, end_h: int) -> pd.Series:
    h = index.tz_convert(TZ).hour
    return normalise(pd.Series(((h >= start_h) & (h < end_h)).astype(float), index=index))


def capacity_factor_shape(gen: pd.Series, cap: pd.Series) -> pd.Series:
    """Historical half-hourly capacity factor -> annual shape (NESO embedded estimates)."""
    cf = (gen / cap.where(cap > 0)).clip(0, 1)
    return normalise(cf)


def valley_fill(load_mw: pd.Series, annual_mwh: float) -> pd.Series:
    """Idealised smart charging: each local day receives an equal share of the annual energy, placed
    in that day's lowest-demand half-hours so the load is flattened from the bottom up (water-filling).
    Returns MW per half-hour; sums to annual_mwh (x 0.5 h)."""
    day = load_mw.index.tz_convert(TZ).normalize()
    days = pd.unique(day)
    e_day = annual_mwh / len(days)
    out = pd.Series(0.0, index=load_mw.index)
    for dd in days:
        m = day == dd
        l = load_mw[m].to_numpy()
        lo, hi = l.min(), l.max() + 2 * e_day / max(1, m.sum()) * m.sum()
        for _ in range(60):                       # bisection on the fill level
            mid = (lo + hi) / 2
            if np.maximum(mid - l, 0).sum() / 2 > e_day:
                hi = mid
            else:
                lo = mid
        out[m] = np.maximum(lo - l, 0)
        out[m] *= e_day / max(out[m].sum() / 2, 1e-9)
    return out
