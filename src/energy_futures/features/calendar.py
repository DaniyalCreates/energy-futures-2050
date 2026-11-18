"""Calendar features in UK local time, including England & Wales bank holidays.

Bank holidays are computed from the statutory rules plus the one-off changes listed below,
so no extra package or network call is needed. England & Wales holidays are used because
they cover ~89% of GB demand; Scottish differences are a documented simplification.
"""
from datetime import date, timedelta

import pandas as pd
from dateutil.easter import easter

TZ = "Europe/London"

# One-off additions and moves, 2009-2026 (gov.uk bank holiday announcements).
SPECIAL = {date(2011, 4, 29), date(2012, 6, 5), date(2022, 6, 3), date(2022, 9, 19), date(2023, 5, 8)}
MOVED = {  # year -> (normal date removed, replacement date)
    2012: (date(2012, 5, 28), date(2012, 6, 4)),   # Spring bank holiday moved for Diamond Jubilee
    2020: (date(2020, 5, 4), date(2020, 5, 8)),    # Early May moved to VE Day
    2022: (date(2022, 5, 30), date(2022, 6, 2)),   # Spring moved for Platinum Jubilee
}


def _first_monday(y, m):
    d = date(y, m, 1)
    return d + timedelta(days=(7 - d.weekday()) % 7)


def _last_monday(y, m):
    d = date(y, m + 1, 1) - timedelta(days=1)
    return d - timedelta(days=d.weekday())


def bank_holidays_ew(year: int) -> set[date]:
    hol = set()
    nyd = date(year, 1, 1)
    hol.add(nyd + timedelta(days={5: 2, 6: 1}.get(nyd.weekday(), 0)))
    e = easter(year)
    hol |= {e - timedelta(days=2), e + timedelta(days=1)}
    hol |= {_first_monday(year, 5), _last_monday(year, 5), _last_monday(year, 8)}
    xmas, boxing = date(year, 12, 25), date(year, 12, 26)
    if xmas.weekday() == 5:      # Sat: Mon 27 + Tue 28
        hol |= {date(year, 12, 27), date(year, 12, 28)}
    elif xmas.weekday() == 6:    # Sun: Mon 26 (Boxing) + Tue 27
        hol |= {date(year, 12, 26), date(year, 12, 27)}
    elif xmas.weekday() == 4:    # Fri: Boxing Sat -> Mon 28
        hol |= {xmas, date(year, 12, 28)}
    else:
        hol |= {xmas, boxing}
    if year in MOVED:
        old, new = MOVED[year]
        hol.discard(old)
        hol.add(new)
    hol |= {d for d in SPECIAL if d.year == year}
    return hol


def calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Features known in advance for any target time (no leakage possible)."""
    local = index.tz_convert(TZ)
    years = range(local.year.min(), local.year.max() + 1)
    hols = set().union(*(bank_holidays_ew(y) for y in years))
    d = pd.Series(local.date, index=index)
    return pd.DataFrame({
        "slot": (local.hour * 2 + local.minute // 30).astype(int),   # local wall-clock half-hour 0..47
        "dow": local.day_of_week.astype(int),
        "month": local.month.astype(int),
        "is_holiday": d.isin(hols).astype(int).to_numpy(),
        # Christmas-New Year period behaves like a long holiday for demand.
        "is_xmas_period": (((local.month == 12) & (local.day >= 24)) | ((local.month == 1) & (local.day <= 2))).astype(int),
    }, index=index)
