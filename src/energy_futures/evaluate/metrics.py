"""Point-forecast metrics (Step 22). All errors in MW unless stated."""
import numpy as np
import pandas as pd

TZ = "Europe/London"


def point_metrics(y: pd.Series, f: pd.Series, peak_threshold: float | None = None) -> dict:
    ok = y.notna() & f.notna()
    y, f = y[ok], f[ok]
    e = f - y
    out = {
        "n": int(ok.sum()),
        "MAE": float(e.abs().mean()),
        "RMSE": float(np.sqrt((e ** 2).mean())),
        "MAPE_pct": float((e.abs() / y).mean() * 100),
        "bias": float(e.mean()),
    }
    # Daily peak: error in the size of each local day's maximum, and whether its timing is within 1 hour.
    day = y.index.tz_convert(TZ).date
    g = pd.DataFrame({"y": y, "f": f, "day": day})
    peaks = g.groupby("day").agg(y_max=("y", "max"), f_max=("f", "max"),
                                 y_at=("y", lambda s: s.idxmax()), f_at=("f", lambda s: s.idxmax()))
    out["daily_peak_MAE"] = float((peaks.f_max - peaks.y_max).abs().mean())
    out["daily_peak_timing_within_1h_pct"] = float(((peaks.f_at - peaks.y_at).abs() <= pd.Timedelta(hours=1)).mean() * 100)
    if peak_threshold is not None:
        hi = y >= peak_threshold
        out["high_demand_MAE"] = float(e[hi].abs().mean()) if hi.any() else float("nan")
        out["high_demand_n"] = int(hi.sum())
    return out
