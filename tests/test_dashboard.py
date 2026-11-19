"""Batch 7: every dashboard page renders without exceptions (Streamlit AppTest, headless)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "dashboard" / "app.py")
PAGES = ["Overview", "Forecasting", "Future scenarios", "Flexibility decisions", "Assumptions & limitations"]


@pytest.mark.skipif(not (ROOT / "outputs" / "optimisation" / "historical_central.csv").exists(), reason="outputs not generated")
@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]
