"""Helpers shared by every subcommand."""

from __future__ import annotations

import argparse
import datetime as _dt
from decimal import Decimal
from typing import Dict, Optional

from ..core.money import ZERO, dec
from ..core.rates import Frequency


def add_output_args(parser: argparse.ArgumentParser) -> None:
    """Attach the output flags every command understands."""
    group = parser.add_argument_group("output")
    group.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    group.add_argument(
        "--csv",
        metavar="PATH",
        help="write the command's primary table to a CSV file ('-' for stdout)",
    )
    group.add_argument(
        "--detail",
        action="store_true",
        help="include the full table in the printed/JSON output, not just the summary",
    )
    group.add_argument("--quiet", action="store_true", help="suppress the human-readable report")


def add_rate_convention_args(parser: argparse.ArgumentParser, *, default_effective: bool) -> None:
    """Let the user state what their annual rate means.

    Loans are quoted nominally (APR / 12); market returns are quoted as an
    effective annual yield.  Each command picks the sensible default and this
    flag makes the other one reachable.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--nominal-rate",
        dest="effective_rate",
        action="store_false",
        help="treat the annual rate as nominal, compounded each period (APR convention)"
        + (" [default]" if not default_effective else ""),
    )
    group.add_argument(
        "--effective-rate",
        dest="effective_rate",
        action="store_true",
        help="treat the annual rate as an effective annual yield"
        + (" [default]" if default_effective else ""),
    )
    parser.set_defaults(effective_rate=default_effective)


def today(args: argparse.Namespace) -> _dt.date:
    """The evaluation date, overridable with ``--as-of`` for reproducible runs."""
    return getattr(args, "as_of", None) or _dt.date.today()


def add_as_of(parser: argparse.ArgumentParser) -> None:
    from ..argtypes import date as date_type

    parser.add_argument(
        "--as-of",
        type=date_type,
        metavar="YYYY-MM-DD",
        help="evaluate as of this date instead of today (makes output reproducible)",
    )


def parse_lump_sums(values: Optional[list]) -> Dict[int, Decimal]:
    """Parse repeated ``--lump-sum N:AMOUNT`` options into ``{period: amount}``."""
    result: Dict[int, Decimal] = {}
    for raw in values or []:
        if ":" not in raw:
            raise argparse.ArgumentTypeError(
                f"--lump-sum expects PAYMENT_NUMBER:AMOUNT, got {raw!r}"
            )
        number_text, amount_text = raw.split(":", 1)
        try:
            number = int(number_text)
            amount = dec(amount_text.replace(",", "").replace("$", "").strip())
        except (ValueError, ArithmeticError):
            raise argparse.ArgumentTypeError(f"could not parse --lump-sum {raw!r}")
        if number < 1:
            raise argparse.ArgumentTypeError("--lump-sum payment number starts at 1")
        if amount <= 0:
            raise argparse.ArgumentTypeError("--lump-sum amount must be positive")
        result[number] = result.get(number, ZERO) + amount
    return result


def freq_adverb(freq: Frequency) -> str:
    """'monthly' -> 'per month' style phrasing for report labels."""
    return {
        Frequency.ANNUAL: "per year",
        Frequency.SEMIANNUAL: "per half-year",
        Frequency.QUARTERLY: "per quarter",
        Frequency.MONTHLY: "per month",
        Frequency.SEMIMONTHLY: "per half-month",
        Frequency.BIWEEKLY: "per two weeks",
        Frequency.WEEKLY: "per week",
        Frequency.DAILY: "per day",
    }[freq]
