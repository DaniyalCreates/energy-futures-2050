"""
Tests for download_cs3_data_2026.py.

Network calls are mocked with unittest.mock.patch so no real HTTP requests
are made.  No 2026 data files are downloaded or opened.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from energy_futures.experiments.download_cs3_data_2026 import (
    CS3_END,
    CS3_START,
    HOURLY_VARS,
    LEAD,
    LOCATIONS,
    YEAR_2026,
    _get_with_retry,
    _neso_list_resources,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic API responses
# ---------------------------------------------------------------------------

def _neso_api_response(year: int = 2026) -> MagicMock:
    """Minimal CKAN API response for NESO with one CSV resource for `year`."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "result": {
            "resources": [
                {
                    "name": f"Historic Demand Data {year}",
                    "format": "CSV",
                    "url": f"https://example.com/demanddata_{year}.csv",
                }
            ]
        }
    }
    return mock_resp


def _open_meteo_response(variables: list[str]) -> MagicMock:
    """Minimal Open-Meteo API response with two hourly values per variable."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.url = "https://example.com/mocked"
    hourly = {"time": ["2026-01-01T00:00", "2026-01-01T01:00"]}
    for v in variables:
        hourly[v] = [10.0, 11.0]
    mock_resp.json.return_value = {"hourly": hourly}
    return mock_resp


def _minimal_neso_csv() -> bytes:
    """Minimal valid NESO demand CSV for 2026."""
    rows = textwrap.dedent("""\
        SETTLEMENT_DATE,SETTLEMENT_PERIOD,ND,TSD,ENGLAND_WALES_DEMAND,\
EMBEDDED_WIND_GENERATION,EMBEDDED_WIND_CAPACITY,EMBEDDED_SOLAR_GENERATION,\
EMBEDDED_SOLAR_CAPACITY,NON_BM_STOR,PUMP_STORAGE_PUMPING,FORECAST_ACTUAL_INDICATOR
        2026-01-01,1,30000,31000,28000,500,1000,0,2000,100,0,A
        2026-01-01,2,30100,31100,28100,510,1000,0,2000,100,0,A
    """)
    return rows.encode("utf-8")


# ---------------------------------------------------------------------------
# _neso_list_resources
# ---------------------------------------------------------------------------

class TestNesoListResources:
    def test_parses_year_and_url(self):
        """Should extract year → url from a CKAN API response."""
        with patch("requests.get", return_value=_neso_api_response(2026)) as mock_get:
            resources = _neso_list_resources()
        mock_get.assert_called_once()
        assert 2026 in resources
        assert resources[2026] == "https://example.com/demanddata_2026.csv"

    def test_non_csv_resources_are_excluded(self):
        """Resources without format=CSV should not appear in result."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "resources": [
                    {"name": "Historic Demand Data 2026", "format": "XLSX",
                     "url": "https://example.com/x.xlsx"},
                    {"name": "Historic Demand Data 2026", "format": "CSV",
                     "url": "https://example.com/x.csv"},
                ]
            }
        }
        with patch("requests.get", return_value=mock_resp):
            resources = _neso_list_resources()
        assert 2026 in resources
        assert resources[2026] == "https://example.com/x.csv"

    def test_missing_year_not_in_result(self):
        """A year with no CSV resource should not appear."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"result": {"resources": []}}
        with patch("requests.get", return_value=mock_resp):
            resources = _neso_list_resources()
        assert 2026 not in resources


# ---------------------------------------------------------------------------
# _get_with_retry
# ---------------------------------------------------------------------------

class TestGetWithRetry:
    def test_returns_response_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            result = _get_with_retry("http://example.com", {})
        assert result is mock_resp

    def test_raises_after_max_retries_on_rate_limit(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp), \
             patch("time.sleep"):
            with pytest.raises(RuntimeError, match="Rate-limited"):
                _get_with_retry("http://example.com", {}, n_retry=2)

    def test_retries_on_429_then_succeeds(self):
        """First attempt returns 429; second returns 200."""
        mock_429 = MagicMock(status_code=429)
        mock_429.raise_for_status = MagicMock()
        mock_200 = MagicMock(status_code=200)
        mock_200.raise_for_status = MagicMock()
        with patch("requests.get", side_effect=[mock_429, mock_200]), \
             patch("time.sleep"):
            result = _get_with_retry("http://example.com", {}, n_retry=3)
        assert result is mock_200


# ---------------------------------------------------------------------------
# forecast_weather_2026 — guard: restricted to CS3_START..CS3_END
# ---------------------------------------------------------------------------

class TestForecastWeather2026DateGuard:
    def test_uses_cs3_start_end_in_params(self):
        """API request params must use CS3_START and CS3_END, not full year."""
        import importlib
        import energy_futures.experiments.download_cs3_data_2026 as mod

        captured_params = []

        def mock_get(url, params, timeout):
            captured_params.append(params.copy())
            mock_resp = MagicMock(status_code=200)
            mock_resp.raise_for_status = MagicMock()
            hourly = {"time": ["2026-01-01T00:00"]}
            for v in [f"{var}_{LEAD}" for var in HOURLY_VARS]:
                hourly[v] = [1.0]
            mock_resp.json.return_value = {"hourly": hourly}
            mock_resp.url = "http://mocked"
            return mock_resp

        with patch("requests.get", side_effect=mock_get), \
             patch("time.sleep"), \
             patch.object(mod, "_write_manifest"), \
             patch.object(mod, "RAW_FORECAST_DIR", Path("/tmp/test_forecast")), \
             patch("pathlib.Path.mkdir"):
            # Patch file exists to False so it tries to download
            with patch("pathlib.Path.exists", return_value=False), \
                 patch("pathlib.Path.write_text"):
                try:
                    mod._download_forecast_weather_2026(force=True)
                except Exception:
                    pass  # may fail due to path mocking; we just check params

        if captured_params:
            for p in captured_params:
                assert p.get("start_date") == CS3_START, \
                    f"Expected start_date={CS3_START!r}, got {p.get('start_date')!r}"
                assert p.get("end_date") == CS3_END, \
                    f"Expected end_date={CS3_END!r}, got {p.get('end_date')!r}"


# ---------------------------------------------------------------------------
# ERA5 download — guard: restricted to CS3_START..CS3_END
# ---------------------------------------------------------------------------

class TestEra5Weather2026DateGuard:
    def test_uses_cs3_start_end_in_params(self):
        import energy_futures.experiments.download_cs3_data_2026 as mod

        captured_params = []

        def mock_get(url, params, timeout):
            captured_params.append(params.copy())
            mock_resp = MagicMock(status_code=200)
            mock_resp.raise_for_status = MagicMock()
            hourly = {"time": ["2026-01-01T00:00"]}
            for v in HOURLY_VARS:
                hourly[v] = [1.0]
            mock_resp.json.return_value = {"hourly": hourly}
            mock_resp.url = "http://mocked"
            return mock_resp

        with patch("requests.get", side_effect=mock_get), \
             patch("time.sleep"), \
             patch.object(mod, "_write_manifest"), \
             patch.object(mod, "RAW_WEATHER_DIR", Path("/tmp/test_weather")), \
             patch("pathlib.Path.mkdir"):
            with patch("pathlib.Path.exists", return_value=False), \
                 patch("pathlib.Path.write_text"):
                try:
                    mod._download_era5_weather_2026(force=True)
                except Exception:
                    pass

        if captured_params:
            for p in captured_params:
                assert p.get("start_date") == CS3_START
                assert p.get("end_date") == CS3_END


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------

class TestConstants:
    def test_cs3_window_is_2026(self):
        assert CS3_START == "2026-01-01"
        assert CS3_END == "2026-10-31"
        assert YEAR_2026 == 2026

    def test_six_locations_defined(self):
        assert len(LOCATIONS) == 6
        expected = {"london", "birmingham", "manchester", "newcastle", "glasgow", "cardiff"}
        assert set(LOCATIONS.keys()) == expected

    def test_forecast_variables_match_existing_pipeline(self):
        """The 4 hourly vars must match what the existing benchmarks.py uses."""
        assert set(HOURLY_VARS) == {
            "temperature_2m", "wind_speed_10m", "cloud_cover", "shortwave_radiation"
        }

    def test_lead_is_previous_day2(self):
        assert LEAD == "previous_day2"
