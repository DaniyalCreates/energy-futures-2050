"""Probabilistic evaluation and rolling conformal calibration (Steps 28-29).

Rolling conformalised quantile regression (CQR): for a central interval [lo, hi] with nominal
coverage 1-a, the conformity score is s = max(lo - y, y - hi). The correction applied to a
forecast is the finite-sample (1-a) quantile of the scores of the previous `window_days` of
OUT-OF-SAMPLE forecasts whose outcomes were known at the issue time. No future outcome is used.
"""
import numpy as np
import pandas as pd

from energy_futures.forecast import task

INTERVALS = {"50": ("q25", "q75"), "80": ("q10", "q90"), "90": ("q05", "q95")}


def pinball(y: pd.Series, Q: pd.DataFrame) -> float:
    losses = []
    for c in Q.columns:
        q = int(c[1:]) / 100
        e = y - Q[c]
        losses.append(np.maximum(q * e, (q - 1) * e).mean())
    return float(np.mean(losses))


def interval_stats(y: pd.Series, Q: pd.DataFrame) -> dict:
    out = {"pinball_mean": pinball(y, Q)}
    for name, (lo, hi) in INTERVALS.items():
        if lo in Q and hi in Q:
            out[f"cover_{name}"] = float(((y >= Q[lo]) & (y <= Q[hi])).mean() * 100)
            out[f"width_{name}"] = float((Q[hi] - Q[lo]).mean())
    return out


def rolling_cqr(y: pd.Series, Q: pd.DataFrame, apply_from: str, window_days: int = 365) -> pd.DataFrame:
    """Return calibrated quantiles for days >= apply_from (local), using only past scores."""
    days = pd.Series(Q.index.tz_convert("Europe/London").tz_localize(None).normalize(), index=Q.index)
    out = Q[days >= pd.Timestamp(apply_from)].copy()
    yq = y.reindex(Q.index)
    for name, (lo, hi) in INTERVALS.items():
        a = 1 - int(name) / 100
        s = np.maximum(Q[lo] - yq, yq - Q[hi])
        for day, rows in out.groupby(days.reindex(out.index)).groups.items():
            # Scores usable for this day: periods whose outcome was public by the day's issue time.
            cutoff = task.train_cutoff(pd.Timestamp(day))
            hist = s[(s.index <= cutoff) & (s.index > cutoff - pd.Timedelta(days=window_days))].dropna()
            n = len(hist)
            c = float(np.quantile(hist, min(1.0, (1 - a) * (n + 1) / n))) if n else 0.0
            out.loc[rows, lo] = Q.loc[rows, lo] - c
            out.loc[rows, hi] = Q.loc[rows, hi] + c
    # Keep quantiles ordered after adjustment.
    out[:] = np.sort(out.to_numpy(), axis=1)
    return out
