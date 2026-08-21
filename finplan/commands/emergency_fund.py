"""``finplan emergency-fund`` -- how big a cushion, and how long to build it."""

from __future__ import annotations

import argparse

from .. import argtypes
from ..core.dates import add_periods
from ..core.money import ONE, ZERO, fmt_money, fmt_years, money
from ..core.rates import Frequency, periodic_rate
from ..output import Report, emit
from ._common import add_as_of, add_output_args, today

NAME = "emergency-fund"
ALIASES = ("emergency",)
HELP = "Size an emergency fund and work out how long it takes to build"


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        aliases=list(ALIASES),
        help=HELP,
        description=(
            "Sizes an emergency fund from your essential monthly spending and shows "
            "how long the current balance would actually last."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--monthly-expenses", type=argtypes.positive_amount, required=True,
                        help="essential spending per month: housing, food, utilities, "
                             "insurance, minimum debt payments")
    parser.add_argument("--months", type=argtypes.positive_int, default=6,
                        help="months of coverage to target")
    parser.add_argument("--current-fund", type=argtypes.nonneg_amount, default=ZERO,
                        help="amount already set aside")
    parser.add_argument("--monthly-contribution", type=argtypes.nonneg_amount, default=ZERO,
                        help="amount added to the fund each month")
    parser.add_argument("--apy", type=argtypes.percentage, default=ZERO,
                        help="annual interest paid on the account, as a percentage")
    parser.add_argument("--income-stability",
                        choices=("stable", "variable", "single-earner", "self-employed"),
                        help="adjusts the recommended coverage for how reliable the income is")
    add_as_of(parser)
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser

#: Rules of thumb for coverage, by how reliable the income is.
STABILITY_MONTHS = {
    "stable": 3,
    "variable": 6,
    "single-earner": 6,
    "self-employed": 12,
}


def run(args) -> int:
    target = money(args.monthly_expenses * args.months)
    gap = target - args.current_fund
    covered = args.current_fund / args.monthly_expenses if args.monthly_expenses else ZERO

    report = Report(
        f"Emergency fund: {args.months} months of {fmt_money(args.monthly_expenses)}",
        f"{fmt_money(args.current_fund)} set aside today",
    )
    report.money("Target", target)
    report.money("Current balance", args.current_fund)
    report.add("Months currently covered", f"{covered:.1f}")
    report.percent("Progress", args.current_fund / target if target else ZERO)

    if gap <= 0:
        report.add("Status", "fully funded")
        report.money("Amount above target", -gap)
        report.note(
            "Cash beyond the target earns little after inflation. Consider directing "
            "the surplus at high-rate debt or long-term investments."
        )
    else:
        report.money("Still to save", gap)
        if args.monthly_contribution > 0:
            rate = periodic_rate(args.apy, Frequency.MONTHLY, effective=True)
            balance = args.current_fund
            months = 0
            while balance < target and months < 1200:
                balance = balance * (ONE + rate) + args.monthly_contribution
                months += 1
            report.section("Building it")
            report.money("Monthly contribution", args.monthly_contribution)
            report.add("Months to fully funded", months)
            report.add("Time to fully funded", fmt_years(months, 12))
            report.add("Fully funded on", add_periods(today(args), months - 1, Frequency.MONTHLY))
        else:
            report.warn(
                "No monthly contribution given, so the gap never closes. "
                "Add --monthly-contribution to see a timeline."
            )

    if args.income_stability:
        recommended = STABILITY_MONTHS[args.income_stability]
        report.section("Coverage guidance")
        report.add("Income stability", args.income_stability)
        report.add("Commonly recommended", f"{recommended} months")
        report.money("That target would be", money(args.monthly_expenses * recommended))
        if recommended > args.months:
            report.warn(
                f"For {args.income_stability} income a {recommended}-month cushion is "
                f"usually advised; you are targeting {args.months}."
            )

    report.table(
        "Coverage at different targets",
        ["Months of coverage", "Target amount", "Gap from current"],
        [
            [m, money(args.monthly_expenses * m), money(args.monthly_expenses * m - args.current_fund)]
            for m in (1, 3, 6, 9, 12)
        ],
    )
    emit(report, args)
    return 0
