"""argparse ``type=`` callables that reject bad input at the boundary.

The original scripts accepted ``--interest-rate -5`` or
``--monthly-contribution 0`` and only failed later with a ZeroDivisionError or
a domain error from ``math.log``.  Validating here turns those into a normal
argparse usage error naming the offending flag.
"""

from __future__ import annotations

import argparse
import datetime as _dt
from decimal import Decimal, InvalidOperation

from .core.dates import parse_date
from .core.money import dec
from .core.rates import Frequency


def _to_decimal(value: str, what: str) -> Decimal:
    try:
        return dec(value.replace(",", "").replace("$", "").strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid {what}")


def amount(value: str) -> Decimal:
    """A monetary amount of any sign.  Accepts ``$1,234.56``."""
    return _to_decimal(value, "amount")


def nonneg_amount(value: str) -> Decimal:
    result = amount(value)
    if result < 0:
        raise argparse.ArgumentTypeError(f"{value!r} must not be negative")
    return result


def positive_amount(value: str) -> Decimal:
    result = amount(value)
    if result <= 0:
        raise argparse.ArgumentTypeError(f"{value!r} must be greater than zero")
    return result


def percentage(value: str) -> Decimal:
    """An annual rate entered as a percentage; returned as a fraction.

    ``6.5`` becomes ``Decimal("0.065")``.  Values above 100 are rejected as
    almost certainly a fraction entered by mistake (``--rate 0.065`` meaning
    6.5% is caught by the low-value hint in the command help instead).
    """
    result = _to_decimal(value.rstrip("%"), "percentage")
    if result < 0:
        raise argparse.ArgumentTypeError(f"rate {value!r} must not be negative")
    if result > 100:
        raise argparse.ArgumentTypeError(
            f"rate {value!r} looks wrong: enter a percentage such as 6.5, not 650"
        )
    return result / 100


def positive_percentage(value: str) -> Decimal:
    result = percentage(value)
    if result <= 0:
        raise argparse.ArgumentTypeError(f"rate {value!r} must be greater than zero")
    return result


def positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number")
    if result <= 0:
        raise argparse.ArgumentTypeError(f"{value!r} must be greater than zero")
    return result


def nonneg_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number")
    if result < 0:
        raise argparse.ArgumentTypeError(f"{value!r} must not be negative")
    return result


def age(value: str) -> int:
    result = nonneg_int(value)
    if result > 120:
        raise argparse.ArgumentTypeError(f"age {value!r} is out of range")
    return result


def years(value: str) -> Decimal:
    """A term in years; fractional terms are allowed."""
    result = _to_decimal(value, "number of years")
    if result <= 0:
        raise argparse.ArgumentTypeError(f"term {value!r} must be greater than zero")
    if result > 100:
        raise argparse.ArgumentTypeError(f"term {value!r} exceeds 100 years")
    return result


def date(value: str) -> _dt.date:
    try:
        return parse_date(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def frequency(value: str) -> Frequency:
    try:
        return Frequency.parse(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))
