"""``finplan invest`` -- project the growth of a contributory portfolio."""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import List

from .. import argtypes
from ..core.money import ONE, ZERO, dec, fmt_money, money
from ..core.rates import Frequency, periodic_rate, real_rate
from ..output import Report, emit
from ._common import add_output_args, add_rate_convention_args, freq_adverb

NAME = "invest"
ALIASES = ("investment",)
HELP = "Project an investment's growth, with fees, raises and inflation"


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        aliases=list(ALIASES),
        help=HELP,
        description=(
            "Projects a lump sum plus recurring contributions forward, net of fund "
            "fees, and reports the result in both nominal and inflation-adjusted "
            "(today's) dollars."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--initial", "--initial-investment", dest="initial",
                        type=argtypes.nonneg_amount, default=ZERO,
                        help="amount invested today")
    parser.add_argument("--contribution", "--monthly-investment", dest="contribution",
                        type=argtypes.nonneg_amount, default=ZERO,
                        help="amount added each period")
    parser.add_argument("--frequency", type=argtypes.frequency, default=Frequency.MONTHLY,
                        help="how often contributions are made and returns compound")
    parser.add_argument("--years", type=argtypes.years, required=True,
                        help="length of the projection")
    parser.add_argument("--return", "--interest-rate", "--annual-return", dest="annual_return",
                        type=argtypes.percentage, required=True,
                        help="expected annual return as a percentage, e.g. 7")
    parser.add_argument("--fees", "--expense-ratio", dest="fees",
                        type=argtypes.percentage, default=ZERO,
                        help="annual fund fees as a percentage, subtracted from the return")
    parser.add_argument("--inflation", type=argtypes.percentage, default=ZERO,
                        help="annual inflation, used to restate the result in today's dollars")
    parser.add_argument("--contribution-growth", type=argtypes.percentage, default=ZERO,
                        help="annual increase in the contribution, e.g. 3 to track a raise")
    parser.add_argument("--contribute-at-start", action="store_true",
                        help="contribute at the start of each period (annuity due) rather than the end")
    add_rate_convention_args(parser, default_effective=True)
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def project(
    initial: Decimal,
    contribution: Decimal,
    periods: int,
    period_rate: Decimal,
    growth_per_period: Decimal,
    due: bool,
) -> List[dict]:
    """Period-by-period roll-forward.

    Iterating rather than using the closed form is what allows a contribution
    that grows over time; for a flat contribution it agrees with
    :func:`finplan.core.tvm.future_value` to the cent.
    """
    balance = initial
    contributed = initial
    rows = []
    current = contribution
    for period in range(1, periods + 1):
        added = current
        if due:
            balance += added
            interest = balance * period_rate
            balance += interest
        else:
            interest = balance * period_rate
            balance += interest + added
        contributed += added
        rows.append(
            {
                "period": period,
                "contribution": money(added),
                "growth": money(interest),
                "balance": money(balance),
                "contributed": money(contributed),
            }
        )
        current *= ONE + growth_per_period
    return rows


def run(args) -> int:
    freq = args.frequency
    periods = int((args.years * freq.per_year).to_integral_value("ROUND_HALF_UP"))
    if periods <= 0:
        raise SystemExit("--years must cover at least one contribution period")

    gross = args.annual_return
    net_annual = gross - args.fees
    if net_annual <= -1:
        raise SystemExit("fees cannot exceed the return by more than 100%")
    rate = periodic_rate(net_annual, freq, effective=args.effective_rate)
    growth_per_period = (
        (ONE + args.contribution_growth) ** (ONE / dec(freq.per_year)) - ONE
        if args.contribution_growth
        else ZERO
    )

    rows = project(
        args.initial, args.contribution, periods, rate, growth_per_period, args.contribute_at_start
    )
    final = rows[-1]["balance"] if rows else args.initial
    contributed = rows[-1]["contributed"] if rows else args.initial
    growth = final - contributed
    real_final = final / ((ONE + args.inflation) ** args.years) if args.inflation else final

    per = freq_adverb(freq)
    report = Report(
        f"Investment projection over {args.years} years",
        f"{fmt_money(args.initial)} today plus {fmt_money(args.contribution)} {per}",
    )
    report.percent("Assumed return", gross,
                   "effective annual" if args.effective_rate else "nominal annual")
    if args.fees:
        report.percent("Fund fees", args.fees)
        report.percent("Net return", net_annual)
    report.percent("Return per period", rate)
    if args.contribution_growth:
        report.percent("Contribution grows", args.contribution_growth, "per year")
        report.money("Final contribution", rows[-1]["contribution"], per)

    report.section("Result")
    report.money("Ending balance", final)
    report.money("Total contributed", contributed)
    report.money("Investment growth", growth)
    report.percent("Growth as share of balance", growth / final if final else ZERO)
    if args.inflation:
        report.money("Ending balance in today's dollars", real_final)
        report.percent("Real return", real_rate(net_annual, args.inflation), "per year")

    if args.initial and args.contribution:
        from ..core.tvm import future_value

        from_initial = money(future_value(rate, periods, ZERO, args.initial))
        report.section("Where the money came from")
        report.money("Grown from the initial investment", from_initial)
        report.money("Grown from contributions", final - from_initial)

    annual: List[list] = []
    per_year = freq.per_year
    for index, row in enumerate(rows):
        if (index + 1) % per_year == 0 or index == len(rows) - 1:
            year = (index + 1) / per_year
            annual.append(
                [
                    f"{year:.2f}".rstrip("0").rstrip("."),
                    row["contributed"],
                    row["balance"] - row["contributed"],
                    row["balance"],
                    row["balance"] / ((ONE + args.inflation) ** dec(year)) if args.inflation else row["balance"],
                ]
            )
    report.table(
        "Year by year",
        ["Year", "Total contributed", "Total growth", "Balance", "Balance in today's dollars"],
        annual,
        preview_rows=40,
    )
    report.note(
        "Projections assume a constant return. Real markets do not deliver one, "
        "and sequence-of-returns risk means the same average can produce very "
        "different outcomes."
    )
    emit(report, args)
    return 0
