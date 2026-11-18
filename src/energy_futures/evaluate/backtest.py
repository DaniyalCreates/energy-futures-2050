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
