"""Payment frequencies and interest-rate conversions.

The original scripts disagreed with each other about what "5% annual return"
means: ``investment_calculator.py`` used ``rate / 12`` (a *nominal* rate) while
``retirement_calculator.py`` used ``(1 + rate) ** (1/12) - 1`` (an *effective*
rate).  Over 30 years those differ by thousands of dollars.  This module makes
the convention explicit and every command states which one it uses.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from .money import ONE, Numeric, dec


class Frequency(Enum):
    """A compounding / payment frequency and its periods per year."""

    ANNUAL = ("annual", 1)
    SEMIANNUAL = ("semiannual", 2)
    QUARTERLY = ("quarterly", 4)
    MONTHLY = ("monthly", 12)
    SEMIMONTHLY = ("semimonthly", 24)
    BIWEEKLY = ("biweekly", 26)
    WEEKLY = ("weekly", 52)
    DAILY = ("daily", 365)

    def __init__(self, label: str, per_year: int) -> None:
        self.label = label
        self.per_year = per_year

    @classmethod
    def parse(cls, value: str | Frequency) -> Frequency:
        if isinstance(value, cls):
            return value
        key = str(value).strip().lower().replace("-", "").replace("_", "")
        aliases = {
            "yearly": cls.ANNUAL,
            "annually": cls.ANNUAL,
            "biweekly": cls.BIWEEKLY,
            "fortnightly": cls.BIWEEKLY,
            "everytwoweeks": cls.BIWEEKLY,
            "twicemonthly": cls.SEMIMONTHLY,
            "semimonthly": cls.SEMIMONTHLY,
        }
        if key in aliases:
            return aliases[key]
        for member in cls:
            if member.label == key or member.name.lower() == key:
                return member
        choices = ", ".join(m.label for m in cls)
        raise ValueError(f"unknown frequency {value!r}; expected one of: {choices}")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.label


def as_rate(value: Numeric) -> Decimal:
    """Interpret a user-supplied rate as a decimal fraction.

    Rates are entered as percentages everywhere in the CLI (``--rate 6.5``
    means 6.5%), so this simply divides by 100.  Kept as a named function so
    the conversion happens in exactly one place.
    """
    return dec(value) / 100


def periodic_rate(annual_rate: Numeric, freq: Frequency, *, effective: bool = False) -> Decimal:
    """Convert an annual rate (as a fraction) to a per-period rate.

    With ``effective=False`` the annual rate is treated as a *nominal* rate
    compounded ``freq.per_year`` times, so the periodic rate is a simple
    division.  This is the convention lenders use to quote loans (APR) and is
    the default.

    With ``effective=True`` the annual rate is treated as the *effective*
    annual yield, so the periodic rate is the ``per_year``-th root.  This is
    the convention for quoted market returns ("the S&P returned 8%").
    """
    rate = dec(annual_rate)
    if not effective:
        return rate / freq.per_year
    if rate <= -1:
        raise ValueError("effective annual rate must be greater than -100%")
    return (ONE + rate) ** (ONE / dec(freq.per_year)) - ONE


def nominal_to_effective(annual_nominal: Numeric, freq: Frequency) -> Decimal:
    """Effective annual yield of a nominal rate compounded ``freq`` times."""
    per_period = dec(annual_nominal) / freq.per_year
    return (ONE + per_period) ** freq.per_year - ONE


def effective_to_nominal(annual_effective: Numeric, freq: Frequency) -> Decimal:
    """Nominal rate compounded ``freq`` times that yields ``annual_effective``."""
    return periodic_rate(annual_effective, freq, effective=True) * freq.per_year


def real_rate(nominal: Numeric, inflation: Numeric) -> Decimal:
    """Inflation-adjusted return via the exact Fisher equation.

    ``(1 + nominal) / (1 + inflation) - 1``.  The common ``nominal - inflation``
    shortcut overstates real returns and the error compounds over a long
    horizon, so the exact form is used.
    """
    infl = dec(inflation)
    if infl <= -1:
        raise ValueError("inflation must be greater than -100%")
    return (ONE + dec(nominal)) / (ONE + infl) - ONE
