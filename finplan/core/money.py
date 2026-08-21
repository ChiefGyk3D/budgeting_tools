"""Money handling.

Every monetary value in :mod:`finplan` is a :class:`decimal.Decimal`.  Binary
floats cannot represent 0.01, so a 30-year amortisation schedule built on
floats accumulates a visible drift in the final rows.  ``Decimal`` with a
generous working precision, quantised to cents only at the boundaries, keeps
the schedule exact.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Union

Numeric = Union[int, float, str, Decimal]

#: Working precision.  Well above cent resolution so that repeated
#: multiplication by a periodic rate does not lose significance.
getcontext().prec = 34

CENT = Decimal("0.01")
ZERO = Decimal("0")
ONE = Decimal("1")


def dec(value: Numeric) -> Decimal:
    """Coerce ``value`` to :class:`Decimal` without inheriting float noise.

    Floats are routed through ``repr`` so that ``0.1`` becomes ``Decimal("0.1")``
    rather than ``Decimal("0.1000000000000000055511151231257827")``.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(repr(value))
    return Decimal(value)


def money(value: Numeric) -> Decimal:
    """Round ``value`` to cents using banker-unfriendly ROUND_HALF_UP.

    Financial statements round half away from zero, not to even, so this
    deliberately differs from Python's default decimal rounding.
    """
    return dec(value).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt_money(value: Numeric, currency: str = "$", places: int = 2) -> str:
    """Format ``value`` as ``$1,234.56``; negatives render as ``-$1,234.56``."""
    amount = dec(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    return f"{sign}{currency}{abs(amount):,.{places}f}"


def fmt_pct(value: Numeric, places: int = 2) -> str:
    """Format a decimal fraction (``0.0725``) as a percentage (``7.25%``)."""
    return f"{dec(value) * 100:.{places}f}%"


def fmt_years(periods: Numeric, periods_per_year: int) -> str:
    """Render a period count as ``"5 years, 3 months"``.

    Partial periods are rounded up: you cannot make three quarters of a
    payment, so a loan needing 63.2 payments takes 64.
    """
    total = int(dec(periods).to_integral_value(rounding="ROUND_CEILING"))
    if periods_per_year == 12:
        years, months = divmod(total, 12)
        parts = []
        if years:
            parts.append(f"{years} year{'s' if years != 1 else ''}")
        if months or not parts:
            parts.append(f"{months} month{'s' if months != 1 else ''}")
        return ", ".join(parts)
    years = total / periods_per_year
    return f"{total} payments ({years:.1f} years)"
