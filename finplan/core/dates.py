"""Payment calendars.

``mortgage_calculator.py`` built payment dates with
``datetime.date(year, month, day)`` carrying the origination day forward, which
raises ``ValueError: day is out of range for month`` for any loan that starts
on the 29th, 30th or 31st.  :func:`add_months` clamps to the end of the month
instead, which is also what servicers do.
"""

from __future__ import annotations

import calendar
import datetime as _dt
from typing import Iterator, List

from .rates import Frequency


def parse_date(value: str) -> _dt.date:
    """Parse ``YYYY-MM-DD`` with an error message that names the offender."""
    try:
        return _dt.datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"invalid date {value!r}: expected YYYY-MM-DD") from exc


def add_months(start: _dt.date, months: int) -> _dt.date:
    """Add ``months`` calendar months, clamping the day to the month end.

    ``add_months(date(2024, 1, 31), 1)`` is 2024-02-29, not an exception.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return _dt.date(year, month, day)


def add_periods(start: _dt.date, periods: int, freq: Frequency) -> _dt.date:
    """Advance ``start`` by ``periods`` of ``freq``."""
    if freq is Frequency.WEEKLY:
        return start + _dt.timedelta(weeks=periods)
    if freq is Frequency.BIWEEKLY:
        return start + _dt.timedelta(weeks=2 * periods)
    if freq is Frequency.DAILY:
        return start + _dt.timedelta(days=periods)
    if freq is Frequency.SEMIMONTHLY:
        # Alternate between the origination day and roughly a fortnight later.
        whole, half = divmod(periods, 2)
        base = add_months(start, whole)
        return base if not half else add_months(start, whole) + _dt.timedelta(days=15)
    months_per_period = 12 // freq.per_year
    return add_months(start, periods * months_per_period)


def payment_dates(start: _dt.date, count: int, freq: Frequency) -> List[_dt.date]:
    """The first ``count`` payment dates, with ``start`` as payment number 1."""
    if count < 0:
        raise ValueError("count must be non-negative")
    return [add_periods(start, i, freq) for i in range(count)]


def iter_payment_dates(start: _dt.date, freq: Frequency) -> Iterator[_dt.date]:
    """Unbounded payment-date generator starting at ``start``."""
    i = 0
    while True:
        yield add_periods(start, i, freq)
        i += 1


def periods_elapsed(start: _dt.date, through: _dt.date, freq: Frequency) -> int:
    """Whole payment periods completed between ``start`` and ``through``.

    Counted by walking the actual calendar rather than by the original code's
    ``years * 26 + months * 2`` approximation, which drifts by two payments a
    year for biweekly schedules.
    """
    if through < start:
        return 0
    if freq in (Frequency.WEEKLY, Frequency.BIWEEKLY, Frequency.DAILY):
        days_per = {Frequency.WEEKLY: 7, Frequency.BIWEEKLY: 14, Frequency.DAILY: 1}[freq]
        return (through - start).days // days_per
    # Month-based: count months then subtract one if the day has not arrived.
    months = (through.year - start.year) * 12 + (through.month - start.month)
    if through.day < min(start.day, calendar.monthrange(through.year, through.month)[1]):
        months -= 1
    months = max(months, 0)
    if freq is Frequency.SEMIMONTHLY:
        return months * 2
    return months // (12 // freq.per_year)
