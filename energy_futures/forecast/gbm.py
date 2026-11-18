"""LightGBM point and quantile forecasters (Steps 25, 28). Hyper-parameters are fixed and
moderate (no search on validation beyond the training-window choice, D-022) to limit
over-fitting to the validation year."""
import lightgbm as lgb
import numpy as np
import pandas as pd

from energy_futures.features.build import CALENDAR, DEMAND_FEATURES, WEATHER_FEATURES

PARAMS = dict(n_estimators=600, learning_rate=0.05, num_leaves=63, min_child_samples=50,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
              random_state=42, n_jobs=-1, verbose=-1)
QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)


def feature_list(use_weather: bool) -> list[str]:
    return CALENDAR + DEMAND_FEATURES + (WEATHER_FEATURES if use_weather else [])


class GBMPoint:
    def __init__(self, use_weather: bool, train_start: str | None = None):
        self.cols = feature_list(use_weather)
        self.train_start = pd.Timestamp(train_start, tz="UTC") if train_start else None

    def fit(self, X, y):
        m = y.notna() & X[self.cols].notna().any(axis=1)
        if self.train_start is not None:
            m &= X.index >= self.train_start
        self.model = lgb.LGBMRegressor(objective="l2", **PARAMS).fit(X.loc[m, self.cols], y[m])
        return self

    def predict(self, X):
        return self.model.predict(X[self.cols])


class GBMQuantile:
    """One LightGBM per quantile; predictions sorted per row so quantiles never cross."""

    def __init__(self, use_weather: bool, train_start: str | None = None, quantiles=QUANTILES):
        self.cols, self.q = feature_list(use_weather), quantiles
        self.train_start = pd.Timestamp(train_start, tz="UTC") if train_start else None

    def fit(self, X, y):
        m = y.notna()
        if self.train_start is not None:
            m &= X.index >= self.train_start
        self.models = {q: lgb.LGBMRegressor(objective="quantile", alpha=q, **PARAMS).fit(X.loc[m, self.cols], y[m])
                       for q in self.q}
        return self

    def predict_quantiles(self, X) -> pd.DataFrame:
        P = np.column_stack([self.models[q].predict(X[self.cols]) for q in self.q])
        return pd.DataFrame(np.sort(P, axis=1), index=X.index, columns=[f"q{int(q*100):02d}" for q in self.q])
