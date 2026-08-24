"""``finplan paychecks`` -- pay calendar and the months with an extra cheque.

Replaces ``biweekly_pay.py``, which hardcoded 26 paydays (a biweekly year can
contain 27), keyed the tally by month *name* so December and the following
January collided, and leaked the output file handle if writing failed.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as _dt
from collections import OrderedDict
from typing import List, Tuple

from .. import argtypes
from ..core.dates import add_periods
from ..core.money import money
from ..core.rates import Frequency
from ..output import Report, emit
from ._common import add_output_args

NAME = "paychecks"
ALIASES = ("pay", "payday")
HELP = "Build a pay calendar and find the months with an extra paycheck"

#: How many paydays a "normal" month has, per frequency.  Months with more
#: than this are the ones with a windfall cheque.
BASELINE_PER_MONTH = {
    Frequency.WEEKLY: 4,
    Frequency.BIWEEKLY: 2,
    Frequency.SEMIMONTHLY: 2,
    Frequency.MONTHLY: 1,
}


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        aliases=list(ALIASES),
        help=HELP,
        description=(
            "Lists every payday in a window and highlights the months containing an "
            "extra paycheck - the months worth earmarking for savings or a debt "
            "payment, because the regular budget is already covered by the usual two."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--first-payday", "--pay-date", dest="first_payday",
                        type=argtypes.date, required=True, metavar="YYYY-MM-DD",
                        help="a known payday to anchor the calendar on")
    parser.add_argument("--frequency", type=argtypes.frequency, default=Frequency.BIWEEKLY,
                        help="biweekly, weekly, semimonthly or monthly")
    window = parser.add_mutually_exclusive_group()
    window.add_argument("--year", type=int,
                        help="restrict to this calendar year (default: the year of --first-payday)")
    window.add_argument("--through", type=argtypes.date, metavar="YYYY-MM-DD",
                        help="list paydays from --first-payday through this date")
    parser.add_argument("--net-pay", type=argtypes.positive_amount,
                        help="take-home pay per cheque, to total the calendar")
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def paydays_in_window(
    anchor: _dt.date, freq: Frequency, start: _dt.date, end: _dt.date
) -> List[_dt.date]:
    """Every payday in ``[start, end]``, walking back from ``anchor`` if needed.

    The anchor does not have to be the first payday of the window; the series
    is extended in both directions so ``--first-payday`` can be any known
    payday.
    """
    if end < start:
        raise ValueError("the end of the window is before the start")
    step = 0
    while add_periods(anchor, step - 1, freq) >= start:
        step -= 1
        if step < -5000:
            break
    dates = []
    while True:
        current = add_periods(anchor, step, freq)
        if current > end:
            break
        if current >= start:
            dates.append(current)
        step += 1
        if step > 5000:
            break
    return dates


def group_by_month(dates: List[_dt.date]) -> "OrderedDict[Tuple[int, int], List[_dt.date]]":
    """Bucket paydays by (year, month) -- not by month name.

    The original grouped on ``strftime('%B')``, so a window spanning a year
    boundary merged the two Januaries into one bucket and reported the wrong
    three-paycheck months.
    """
    buckets: "OrderedDict[Tuple[int, int], List[_dt.date]]" = OrderedDict()
    for date in dates:
        buckets.setdefault((date.year, date.month), []).append(date)
    return buckets


def run(args) -> int:
    freq = args.frequency
    if freq not in BASELINE_PER_MONTH:
        raise SystemExit(
            f"--frequency {freq.label} is not a payroll frequency; "
            f"choose one of: {', '.join(f.label for f in BASELINE_PER_MONTH)}"
        )

    if args.through:
        start, end = args.first_payday, args.through
        window_label = f"{start.isoformat()} through {end.isoformat()}"
    else:
        year = args.year or args.first_payday.year
        start, end = _dt.date(year, 1, 1), _dt.date(year, 12, 31)
        window_label = f"calendar year {year}"

    dates = paydays_in_window(args.first_payday, freq, start, end)
    if not dates:
        raise SystemExit(f"No paydays fall in {window_label}.")

    buckets = group_by_month(dates)
    baseline = BASELINE_PER_MONTH[freq]
    extra_months = [(key, days) for key, days in buckets.items() if len(days) > baseline]

    report = Report(
        f"Pay calendar: {freq.label} paydays, {window_label}",
        f"Anchored on {args.first_payday.isoformat()}",
    )
    report.add("Paydays in window", len(dates))
    report.add("First payday", dates[0])
    report.add("Last payday", dates[-1])
    if args.net_pay:
        report.money("Net pay per cheque", args.net_pay)
        report.money("Total net pay in window", money(args.net_pay * len(dates)))
        report.money(
            "Average per month",
            money(args.net_pay * len(dates) / max(len(buckets), 1)),
        )

    report.section(f"Months with more than {baseline} paychecks")
    if extra_months:
        for (year, month), days in extra_months:
            label = f"{calendar.month_name[month]} {year}"
            value = f"{len(days)} paychecks on {', '.join(d.strftime('%d') for d in days)}"
            report.add(label, value)
        if args.net_pay:
            windfall = money(args.net_pay * sum(len(d) - baseline for _, d in extra_months))
            report.money("Extra pay across those months", windfall)
            report.note(
                "The regular budget is already covered by the usual paychecks, so this "
                "is the natural money to send at debt, savings or an annual bill."
            )
    else:
        report.add("None", f"every month in this window has exactly {baseline}")

    report.table(
        "Paydays",
        ["Date", "Weekday", "Month", "Number in month"] + (["Net pay"] if args.net_pay else []),
        [
            [
                date,
                date.strftime("%A"),
                date.strftime("%Y-%m"),
                buckets[(date.year, date.month)].index(date) + 1,
            ]
            + ([args.net_pay] if args.net_pay else [])
            for date in dates
        ],
        preview_rows=30,
    )
    report.table(
        "Paychecks per month",
        ["Month", "Paychecks"] + (["Net pay"] if args.net_pay else []),
        [
            [f"{calendar.month_name[month]} {year}", len(days)]
            + ([money(args.net_pay * len(days))] if args.net_pay else [])
            for (year, month), days in buckets.items()
        ],
    )
    emit(report, args)
    return 0
