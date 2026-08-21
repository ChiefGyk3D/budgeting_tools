import datetime as dt

import pytest

from finplan.core.dates import (
    add_months,
    add_periods,
    parse_date,
    payment_dates,
    periods_elapsed,
)
from finplan.core.rates import Frequency


def test_add_months_clamps_to_month_end():
    """mortgage_calculator.py raised ValueError here for any 29th-31st loan."""
    assert add_months(dt.date(2024, 1, 31), 1) == dt.date(2024, 2, 29)
    assert add_months(dt.date(2023, 1, 31), 1) == dt.date(2023, 2, 28)
    assert add_months(dt.date(2024, 3, 31), 1) == dt.date(2024, 4, 30)


def test_add_months_crosses_years_in_both_directions():
    assert add_months(dt.date(2024, 1, 31), 13) == dt.date(2025, 2, 28)
    assert add_months(dt.date(2024, 3, 15), -4) == dt.date(2023, 11, 15)


def test_payment_dates_never_raise_for_a_month_end_loan():
    dates = payment_dates(dt.date(2024, 1, 31), 14, Frequency.MONTHLY)
    assert dates[0] == dt.date(2024, 1, 31)
    assert dates[1] == dt.date(2024, 2, 29)
    assert dates[13] == dt.date(2025, 2, 28)
    assert dates == sorted(dates)


def test_add_periods_by_frequency():
    start = dt.date(2026, 1, 1)
    assert add_periods(start, 1, Frequency.BIWEEKLY) == dt.date(2026, 1, 15)
    assert add_periods(start, 1, Frequency.WEEKLY) == dt.date(2026, 1, 8)
    assert add_periods(start, 1, Frequency.QUARTERLY) == dt.date(2026, 4, 1)
    assert add_periods(start, 1, Frequency.ANNUAL) == dt.date(2027, 1, 1)


def test_periods_elapsed_walks_the_calendar():
    start = dt.date(2020, 1, 15)
    assert periods_elapsed(start, dt.date(2021, 1, 14), Frequency.MONTHLY) == 11
    assert periods_elapsed(start, dt.date(2021, 1, 15), Frequency.MONTHLY) == 12
    assert periods_elapsed(start, dt.date(2019, 1, 1), Frequency.MONTHLY) == 0


def test_periods_elapsed_biweekly_beats_the_old_approximation():
    """The original used years*26 + months*2, which drifts by two a year."""
    start, end = dt.date(2020, 1, 1), dt.date(2021, 1, 1)
    exact = periods_elapsed(start, end, Frequency.BIWEEKLY)
    assert exact == 26  # 366 days // 14
    old_approximation = 1 * 26 + 0 * 2
    assert exact == old_approximation  # equal at exactly one year...
    two_years = periods_elapsed(start, dt.date(2022, 7, 1), Frequency.BIWEEKLY)
    assert two_years == 65  # ...but 2*26 + 6*2 = 64 under the old formula
    assert two_years != 2 * 26 + 6 * 2


def test_parse_date_rejects_junk_with_a_useful_message():
    assert parse_date(" 2026-03-05 ") == dt.date(2026, 3, 5)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_date("03/05/2026")
    with pytest.raises(ValueError):
        parse_date("2026-02-31")
