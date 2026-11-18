"""Leakage-safe expanding-window backtest (Step 21).

The evaluation period is split into blocks (monthly by default). For each block the model is
refit on every target whose outcome was known at the issue time of the block's first forecast
(`task.train_cutoff`), then forecasts every day in the block. Features themselves are checked
by `task.assert_no_leakage`. Within a block, lags still come only from D-2 and D-7, so later days
in the block never use information unavailable at their own issue time.
"""
import pandas as pd

from energy_futures.forecast import task

TZ = "Europe/London"


def blocks(start: str, end: str, freq: str = "MS") -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    starts = pd.date_range(start, end, freq=freq)
    if len(starts) == 0 or starts[0] != pd.Timestamp(start):
        starts = pd.DatetimeIndex([pd.Timestamp(start)]).append(starts)
    ends = list(starts[1:] - pd.Timedelta(days=1)) + [pd.Timestamp(end)]
    return list(zip(starts, ends))


def local_days(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(index.tz_convert(TZ).tz_localize(None).normalize(), index=index)


def run(model_factory, X: pd.DataFrame, y: pd.Series, eval_start: str, eval_end: str,
        train_start: str | None = None, freq: str = "MS") -> tuple[pd.Series, list[dict]]:
    task.assert_no_leakage(X.index)
    days = local_days(X.index)
    preds, log = [], []
    for b0, b1 in blocks(eval_start, eval_end, freq):
        cutoff = task.train_cutoff(b0)
        tr = X.index <= cutoff
        if train_start:
            tr &= X.index >= pd.Timestamp(train_start, tz="UTC")
        te = ((days >= b0) & (days <= b1)).to_numpy()
        assert X.index[tr].max() < X.index[te].min(), "training overlaps evaluation"
        m = model_factory().fit(X[tr], y[tr])
        preds.append(pd.Series(m.predict(X[te]), index=X.index[te]))
        log.append({"block_start": str(b0.date()), "train_end_utc": str(X.index[tr].max()),
                    "n_train": int(tr.sum()), "n_eval": int(te.sum())})
    return pd.concat(preds), log


def run_multi(model_factory, X_fit: pd.DataFrame, y: pd.Series, X_pred: dict[str, pd.DataFrame],
              eval_start: str, eval_end: str, freq: str = "MS", method: str = "predict"):
    """Like `run`, but each refit model predicts from several input sets (e.g. the same model fed
    observed vs forecast weather). Training always uses X_fit rows up to the leakage-safe cutoff."""
    task.assert_no_leakage(X_fit.index)
    days = local_days(X_fit.index)
    out = {k: [] for k in X_pred}
    log = []
    for b0, b1 in blocks(eval_start, eval_end, freq):
        tr = X_fit.index <= task.train_cutoff(b0)
        te_idx = X_fit.index[((days >= b0) & (days <= b1)).to_numpy()]
        assert X_fit.index[tr].max() < te_idx.min(), "training overlaps evaluation"
        m = model_factory().fit(X_fit[tr], y[tr])
        for k, Xp in X_pred.items():
            p = getattr(m, method)(Xp.reindex(te_idx))
            out[k].append(p if isinstance(p, pd.DataFrame) else pd.Series(p, index=te_idx))
        log.append({"block_start": str(b0.date()), "train_end_utc": str(X_fit.index[tr].max()), "n_eval": len(te_idx)})
    return {k: pd.concat(v) for k, v in out.items()}, log
