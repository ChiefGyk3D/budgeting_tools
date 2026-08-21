"""``finplan retire`` -- accumulation projection and required savings rate."""

from __future__ import annotations

import argparse

from .. import argtypes
from ..core.money import ONE, ZERO, dec, fmt_money, money
from ..core.rates import Frequency, periodic_rate, real_rate
from ..core.tvm import contribution_for_goal, future_value, present_value
from ..output import Report, emit
from ._common import add_output_args, add_rate_convention_args

NAME = "retire"
ALIASES = ("retirement",)
HELP = "Project retirement savings, or solve for the contribution you need"


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        aliases=list(ALIASES),
        help=HELP,
        description=(
            "Projects savings to your retirement date and, if you name a target or a "
            "desired retirement income, solves for the monthly contribution that "
            "reaches it. Results are shown in both nominal and today's dollars."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    who = parser.add_argument_group("timeline")
    who.add_argument("--current-age", type=argtypes.age, required=True)
    who.add_argument("--retirement-age", type=argtypes.age, required=True)
    who.add_argument("--life-expectancy", type=argtypes.age, default=95,
                     help="age the money must last to")

    balance = parser.add_argument_group("savings")
    balance.add_argument("--current-savings", type=argtypes.nonneg_amount, default=ZERO,
                         help="retirement balance today")
    balance.add_argument("--monthly-contribution", type=argtypes.nonneg_amount,
                         help="what you contribute each month, including any employer match")
    balance.add_argument("--employer-match", type=argtypes.nonneg_amount, default=ZERO,
                         help="employer contribution each month, added to yours")
    balance.add_argument("--contribution-growth", type=argtypes.percentage, default=ZERO,
                         help="annual increase in your contribution, e.g. 3")

    goal = parser.add_argument_group("goal (give at most one)")
    goal.add_argument("--target", type=argtypes.positive_amount,
                      help="nominal balance you want at retirement")
    goal.add_argument("--annual-spending", type=argtypes.positive_amount,
                      help="annual retirement income you want, in TODAY's dollars")

    assumptions = parser.add_argument_group("assumptions")
    assumptions.add_argument("--annual-return", type=argtypes.percentage, default=argtypes.percentage("7"),
                             help="expected annual return before retirement, as a percentage")
    assumptions.add_argument("--retirement-return", type=argtypes.percentage,
                             help="expected annual return during retirement (default: --annual-return minus 2 points)")
    assumptions.add_argument("--inflation", type=argtypes.percentage, default=argtypes.percentage("3"),
                             help="annual inflation, as a percentage")
    assumptions.add_argument("--withdrawal-rate", type=argtypes.percentage,
                             default=argtypes.percentage("4"),
                             help="safe withdrawal rate used for the sustainable-income estimate")
    assumptions.add_argument("--other-income", type=argtypes.nonneg_amount, default=ZERO,
                             help="annual pension/Social Security in today's dollars, which reduces what savings must cover")
    add_rate_convention_args(parser, default_effective=True)
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def run(args) -> int:
    if args.retirement_age <= args.current_age:
        raise SystemExit(
            f"--retirement-age ({args.retirement_age}) must be greater than "
            f"--current-age ({args.current_age}); there is no time left to save."
        )
    if args.life_expectancy <= args.retirement_age:
        raise SystemExit(
            f"--life-expectancy ({args.life_expectancy}) must be greater than "
            f"--retirement-age ({args.retirement_age})."
        )
    if args.target and args.annual_spending:
        raise SystemExit("give either --target or --annual-spending, not both")

    years_to_retire = args.retirement_age - args.current_age
    years_in_retirement = args.life_expectancy - args.retirement_age
    months = years_to_retire * 12
    freq = Frequency.MONTHLY
    rate = periodic_rate(args.annual_return, freq, effective=args.effective_rate)
    contribution = (args.monthly_contribution or ZERO) + args.employer_match
    deflator = (ONE + args.inflation) ** years_to_retire

    report = Report(
        f"Retirement plan: age {args.current_age} to {args.retirement_age}",
        f"{years_to_retire} years of saving, {years_in_retirement} years of retirement",
    )
    report.money("Current savings", args.current_savings)
    report.percent("Assumed return", args.annual_return,
                   "effective annual" if args.effective_rate else "nominal annual")
    report.percent("Assumed inflation", args.inflation)
    report.percent("Real return", real_rate(args.annual_return, args.inflation), "per year")

    # -- the target, in nominal dollars at the retirement date ---------------
    target = None
    if args.target:
        target = args.target
        target_basis = "your --target"
    elif args.annual_spending:
        covered_today = max(args.annual_spending - args.other_income, ZERO)
        if covered_today == 0:
            raise SystemExit(
                "--other-income already covers --annual-spending; no retirement savings are needed"
            )
        target = money(covered_today * deflator / args.withdrawal_rate)
        target_basis = (
            f"{fmt_money(covered_today)}/yr in today's dollars at a "
            f"{args.withdrawal_rate * 100:.1f}% withdrawal rate, inflated to age {args.retirement_age}"
        )

    # -- projection from the stated contribution ----------------------------
    projected = None
    if args.monthly_contribution is not None or args.current_savings:
        if args.contribution_growth:
            balance = args.current_savings
            monthly = contribution
            growth_per_month = (ONE + args.contribution_growth) ** (ONE / dec(12)) - ONE
            for _ in range(months):
                balance = balance * (ONE + rate) + monthly
                monthly *= ONE + growth_per_month
            projected = money(balance)
        else:
            projected = money(future_value(rate, months, contribution, args.current_savings))

        report.section("Projection")
        report.money("Monthly contribution", contribution,
                     f"including {fmt_money(args.employer_match)} employer match"
                     if args.employer_match else None)
        report.money(f"Balance at age {args.retirement_age}", projected)
        report.money("In today's dollars", money(projected / deflator))
        report.money("Total contributed", money(contribution * months + args.current_savings))
        report.money(
            "Investment growth",
            money(projected - contribution * months - args.current_savings),
        )
        sustainable = money(projected * args.withdrawal_rate)
        report.money(
            f"Sustainable income at {args.withdrawal_rate * 100:.1f}%", sustainable, "per year"
        )
        report.money("...in today's dollars", money(sustainable / deflator), "per year")
        report.money("...per month in today's dollars", money(sustainable / deflator / 12))

        # Does the money actually last? Draw down at the retirement-phase return.
        retire_return = args.retirement_return if args.retirement_return is not None else max(
            args.annual_return - dec("0.02"), ZERO
        )
        real_retire = real_rate(retire_return, args.inflation)
        monthly_real = periodic_rate(real_retire, freq, effective=True)
        withdrawable = present_value(monthly_real, years_in_retirement * 12, ONE)
        if withdrawable > 0:
            monthly_income = money((projected / deflator) / withdrawable)
            report.money(
                f"Depleting over {years_in_retirement} years",
                monthly_income,
                "per month in today's dollars, balance reaches zero at "
                f"age {args.life_expectancy}",
            )

    # -- what the target requires -------------------------------------------
    if target is not None:
        report.section("Target")
        report.money(f"Needed at age {args.retirement_age}", target, target_basis)
        report.money("In today's dollars", money(target / deflator))
        required = money(contribution_for_goal(rate, months, target, args.current_savings))
        if required <= 0:
            report.add("Required monthly contribution", "none")
            report.note(
                "Your current savings alone reach the target at the assumed return. "
                "Anything you add is a margin of safety."
            )
        else:
            report.money("Required monthly contribution", required)
            report.money("Required annual contribution", money(required * 12))
        if projected is not None:
            gap = target - projected
            if gap > 0:
                report.money("Shortfall at retirement", gap)
                report.money("Extra needed each month", money(max(required - contribution, ZERO)))
                report.warn(
                    f"On the current plan you reach {fmt_money(projected)}, which is "
                    f"{fmt_money(gap)} short of {fmt_money(target)}."
                )
            else:
                report.money("Surplus at retirement", -gap)

    if args.other_income:
        report.section("Other income")
        report.money("Pension / Social Security", args.other_income, "per year, today's dollars")

    # -- year by year --------------------------------------------------------
    rows = []
    balance = args.current_savings
    monthly = contribution
    growth_per_month = (
        (ONE + args.contribution_growth) ** (ONE / dec(12)) - ONE
        if args.contribution_growth else ZERO
    )
    for year in range(1, years_to_retire + 1):
        for _ in range(12):
            balance = balance * (ONE + rate) + monthly
            monthly *= ONE + growth_per_month
        rows.append(
            [
                args.current_age + year,
                money(balance),
                money(balance / ((ONE + args.inflation) ** year)),
                money(balance * args.withdrawal_rate / ((ONE + args.inflation) ** year)),
            ]
        )
    report.table(
        "Balance by age",
        ["Age", "Balance", "Balance in today's dollars", "Sustainable income (today's dollars)"],
        rows,
        preview_rows=45,
    )
    report.note(
        "The withdrawal rate is a planning heuristic, not a guarantee; it assumes a "
        "diversified portfolio and does not model taxes, health costs or market sequence."
    )
    emit(report, args)
    return 0
