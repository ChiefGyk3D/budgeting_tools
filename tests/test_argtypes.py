import argparse
import datetime as dt
from decimal import Decimal

import pytest

from finplan import argtypes


def test_amount_accepts_formatted_currency():
    assert argtypes.amount("$1,234.56") == Decimal("1234.56")
    assert argtypes.nonneg_amount("0") == Decimal("0")


@pytest.mark.parametrize("value", ["abc", "", "1.2.3"])
def test_amount_rejects_junk(value):
    with pytest.raises(argparse.ArgumentTypeError):
        argtypes.amount(value)


def test_positive_amount_rejects_zero_and_negatives():
    with pytest.raises(argparse.ArgumentTypeError, match="greater than zero"):
        argtypes.positive_amount("0")
    with pytest.raises(argparse.ArgumentTypeError):
        argtypes.nonneg_amount("-5")


def test_percentage_converts_and_bounds():
    assert argtypes.percentage("6.5") == Decimal("0.065")
    assert argtypes.percentage("6.5%") == Decimal("0.065")
    with pytest.raises(argparse.ArgumentTypeError, match="must not be negative"):
        argtypes.percentage("-1")
    with pytest.raises(argparse.ArgumentTypeError, match="looks wrong"):
        argtypes.percentage("650")


def test_years_and_age_bounds():
    assert argtypes.years("30") == Decimal("30")
    assert argtypes.years("2.5") == Decimal("2.5")
    with pytest.raises(argparse.ArgumentTypeError):
        argtypes.years("0")
    with pytest.raises(argparse.ArgumentTypeError, match="exceeds 100"):
        argtypes.years("150")
    with pytest.raises(argparse.ArgumentTypeError, match="out of range"):
        argtypes.age("200")


def test_date_and_frequency():
    assert argtypes.date("2026-03-05") == dt.date(2026, 3, 5)
    with pytest.raises(argparse.ArgumentTypeError, match="YYYY-MM-DD"):
        argtypes.date("March 5 2026")
    assert argtypes.frequency("bi-weekly").per_year == 26
    with pytest.raises(argparse.ArgumentTypeError, match="unknown frequency"):
        argtypes.frequency("hourly")
