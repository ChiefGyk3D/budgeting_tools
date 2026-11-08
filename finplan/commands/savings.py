"""``finplan savings`` -- reaching a savings goal, with interest."""

from __future__ import annotations

import argparse

from .. import argtypes
from ..core.dates import add_periods
from ..core.money import ONE, ZERO, fmt_money, fmt_years, money
from ..core.rates import Frequency, periodic_rate
from ..core.tvm import contribution_for_goal
from ..output import Report, emit
from ._common import (
    add_as_of,
    add_output_args,
    add_rate_convention_args,
    freq_adverb,
    today,
)

NAME = "savings"
ALIASES = ("goal",)
HELP = "Time to reach a savings goal, or the contribution a deadline requires"


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        aliases=list(ALIASES),
        help=HELP,
        description=(
            "Works out how long a savings goal takes at a given contribution, or "
            "what contribution a deadline requires. Interest is included, so the "
            "answer is not simply (goal - saved) / contribution."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--goal", type=argtypes.positive_amount, required=True,
                        help="amount you want to have saved")
    parser.add_argument("--current-savings", type=argtypes.nonneg_amount, default=ZERO,
                        help="amount already saved")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--contribution", "--monthly-contribution", dest="contribution",
                        type=argtypes.nonneg_amount,
                        help="amount you save each period")
    target.add_argument("--by-date", type=argtypes.date, metavar="YYYY-MM-DD",
                        help="solve for the contribution needed to hit the goal by this date")
    parser.add_argument("--apy", "--rate", dest="apy", type=argtypes.percentage, default=ZERO,
                        help="annual interest earned on the balance, as a percentage")
    parser.add_argument("--frequency", type=argtypes.frequency, default=Frequency.MONTHLY,
                        help="how often you contribute")
    add_as_of(parser)
    add_rate_convention_args(parser, default_effective=True)
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def run(args) -> int:
    freq = args.frequency
    start = today(args)
    rate = periodic_rate(args.apy, freq, effective=args.effective_rate)
    per = freq_adverb(freq)
    remaining = args.goal - args.current_savings

    report = Report(
        f"Savings goal: {fmt_money(args.goal)}",
        f"{fmt_money(args.current_savings)} saved so far",
    )
    report.money("Still to find", max(remaining, ZERO))
    if args.apy:
        report.percent("Interest", args.apy, "annual")

    if remaining <= 0:
        report.add("Status", "goal already reached")
        report.money("Amount over the goal", -remaining)
        emit(report, args)
        return 0

    if args.by_date:
        if args.by_date <= start:
            raise SystemExit(f"--by-date {args.by_date.isoformat()} must be in the future")
        days = (args.by_date - start).days
        periods = max(int(days / 365.25 * freq.per_year), 1)
        required = money(contribution_for_goal(rate, periods, args.goal, args.current_savings))
        report.section("To hit the deadline")
        report.add("Deadline", args.by_date)
        report.add("Periods available", periods)
        report.money(f"Contribution needed ({per})", max(required, ZERO))
        if freq is not Frequency.MONTHLY:
            report.money("Contribution needed per month",
                         max(money(required * freq.per_year / 12), ZERO))
        total = money(required * periods)
        report.money("Total you will contribute", max(total, ZERO))
        report.money("Interest earned", money(args.goal - args.current_savings - max(total, ZERO)))
        if required <= 0:
            report.note("Your current balance already grows to the goal by that date.")
        emit(report, args)
        return 0

    contribution = args.contribution
    if contribution <= 0 and rate <= 0:
        raise SystemExit(
            "With no contribution and no interest the balance never changes. "
            "Give --contribution above zero or an --apy."
        )

    periods = 0
    balance = args.current_savings
    max_periods = freq.per_year * 100
    while balance < args.goal and periods < max_periods:
        balance = balance * (ONE + rate) + contribution
        periods += 1
    if balance < args.goal:
        raise SystemExit(
            f"At {fmt_money(contribution)} {per} the goal is not reached within 100 years. "
            "Increase the contribution."
        )

    contributed = money(contribution * periods)
    report.section("At your current pace")
    report.money(f"Contribution ({per})", contribution)
    report.add("Periods to goal", periods)
    report.add("Time to goal", fmt_years(periods, freq.per_year))
    report.add("Goal reached on", add_periods(start, periods - 1, freq))
    report.money("Ending balance", money(balance))
    report.money("Total contributed", contributed)
    report.money("Interest earned", money(balance - args.current_savings - contributed))

    if args.apy:
        no_interest = int(-(-remaining // contribution)) if contribution > 0 else None
        if no_interest:
            report.add("Periods if interest were ignored", no_interest,
                       f"{no_interest - periods} more than with interest")

    rows = []
    for bump in (money(25), money(50), money(100), money(250)):
        candidate = contribution + bump
        trial_balance = args.current_savings
        trial_periods = 0
        while trial_balance < args.goal and trial_periods < max_periods:
            trial_balance = trial_balance * (ONE + rate) + candidate
            trial_periods += 1
        rows.append(
            [
                candidate,
                trial_periods,
                add_periods(start, trial_periods - 1, freq),
                periods - trial_periods,
            ]
        )
    report.table(
        "If you saved more",
        ["Contribution", "Periods", "Goal reached on", "Periods sooner"],
        rows,
    )
    emit(report, args)
    return 0
