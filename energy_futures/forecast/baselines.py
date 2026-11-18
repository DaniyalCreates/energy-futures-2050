"""Baseline forecasters (Steps 19-20). Each model: fit(X, y) then predict(X)."""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


class SeasonalNaive:
    """Forecast = value at the same local time `days` earlier (no fitting)."""

    def __init__(self, days: int):
        self.col = f"lag_d{days}"

    def fit(self, X, y):
        return self

    def predict(self, X):
        return X[self.col].to_numpy()


CATEGORICAL = ["slot", "dow"]
WEATHER = ["hdd", "cdd", "shortwave_radiation_gb_mean", "wind_speed_10m_gb_mean", "cloud_cover_gb_mean"]


def add_weather_terms(X: pd.DataFrame) -> pd.DataFrame:
    """Heating/cooling degree terms (15.5 C / 18 C UK conventions) make the temperature response
    piecewise-linear, which a plain linear model cannot otherwise represent."""
    X = X.copy()
    t = X["temperature_2m_gb_mean"]
    X["hdd"] = (15.5 - t).clip(lower=0)
    X["cdd"] = (t - 18.0).clip(lower=0)
    return X


class LinearBaseline:
    """OLS on calendar dummies + lagged demand (+ optionally weather).
    use_weather=True uses observed weather at the target time ('perfect-weather', D-009)."""

    def __init__(self, use_weather: bool):
        self.use_weather = use_weather
        num = ["lag_d2", "lag_d7", "is_holiday", "is_xmas_period"] + (WEATHER if use_weather else [])
        self.cols = CATEGORICAL + num
        self.model = Pipeline([
            ("prep", ColumnTransformer([("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), CATEGORICAL)],
                                       remainder="passthrough")),
            ("ols", LinearRegression()),
        ])

    def _X(self, X):
        return (add_weather_terms(X) if self.use_weather else X)[self.cols]

    def fit(self, X, y):
        Xf = self._X(X)
        ok = Xf.notna().all(axis=1) & y.notna()
        self.n_train_ = int(ok.sum())
        self.model.fit(Xf[ok], y[ok])
        return self

    def predict(self, X):
        Xf = self._X(X)
        out = np.full(len(Xf), np.nan)
        ok = Xf.notna().all(axis=1).to_numpy()
        out[ok] = self.model.predict(Xf[ok])
        return out


def make_models() -> dict:
    return {
        "naive_d7": SeasonalNaive(7),
        "naive_d2": SeasonalNaive(2),
        "linear_calendar": LinearBaseline(use_weather=False),
        "linear_weather_PW": LinearBaseline(use_weather=True),   # PW = perfect-weather
    }
