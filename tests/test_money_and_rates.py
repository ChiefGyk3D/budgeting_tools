from decimal import Decimal

import pytest

from finplan.core.money import dec, fmt_money, fmt_pct, fmt_years, money
from finplan.core.rates import (
    Frequency,
    as_rate,
    effective_to_nominal,
    nominal_to_effective,
    periodic_rate,
    real_rate,
)


def test_dec_does_not_inherit_float_noise():
    assert dec(0.1) == Decimal("0.1")
    assert dec(0.1) + dec(0.2) == dec(0.3)


def test_money_rounds_half_up_not_half_even():
    assert money("0.125") == Decimal("0.13")
    assert money("0.135") == Decimal("0.14")
    assert money("-0.125") == Decimal("-0.13")


@pytest.mark.parametrize(
    "value,expected",
    [(1234.5, "$1,234.50"), (-1234.567, "-$1,234.57"), (0, "$0.00"), (1e6, "$1,000,000.00")],
)
def test_fmt_money(value, expected):
    assert fmt_money(value) == expected


def test_fmt_pct_and_years():
    assert fmt_pct(Decimal("0.0725")) == "7.25%"
    assert fmt_years(12, 12) == "1 year"
    assert fmt_years(0, 12) == "0 months"
    # Partial periods round up: you cannot make 0.2 of a payment.
    assert fmt_years(Decimal("63.2"), 12) == "5 years, 4 months"


def test_frequency_parsing_accepts_common_spellings():
    assert Frequency.parse("bi-weekly") is Frequency.BIWEEKLY
    assert Frequency.parse("MONTHLY") is Frequency.MONTHLY
    assert Frequency.parse("yearly") is Frequency.ANNUAL
    assert Frequency.parse(Frequency.WEEKLY) is Frequency.WEEKLY
    with pytest.raises(ValueError, match="unknown frequency"):
        Frequency.parse("hourly")


def test_as_rate_converts_percentage_to_fraction():
    assert as_rate(6.5) == Decimal("0.065")


def test_nominal_and_effective_are_distinct_conventions():
    """The bug the original scripts had: two files, two different meanings."""
    nominal = periodic_rate(as_rate(6), Frequency.MONTHLY)
    effective = periodic_rate(as_rate(6), Frequency.MONTHLY, effective=True)
    assert nominal == Decimal("0.005")
    assert effective < nominal
    # Compounding the effective monthly rate 12 times returns the annual rate.
    assert (1 + effective) ** 12 - 1 == pytest.approx(Decimal("0.06"), abs=Decimal("1e-15"))


def test_nominal_effective_round_trip():
    annual = as_rate(6)
    eff = nominal_to_effective(annual, Frequency.MONTHLY)
    assert eff > annual
    assert effective_to_nominal(eff, Frequency.MONTHLY) == pytest.approx(
        annual, abs=Decimal("1e-20")
    )


def test_real_rate_uses_exact_fisher_not_subtraction():
    exact = real_rate(as_rate(7), as_rate(3))
    assert exact < as_rate(4)  # the naive 7 - 3 = 4 overstates it
    assert exact == pytest.approx(Decimal("0.0388349514563107"), abs=Decimal("1e-12"))


def test_effective_rate_rejects_impossible_input():
    with pytest.raises(ValueError):
        periodic_rate(Decimal("-1.5"), Frequency.MONTHLY, effective=True)
