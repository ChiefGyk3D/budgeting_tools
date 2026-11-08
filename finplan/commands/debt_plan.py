"""``finplan debt-plan`` -- avalanche vs snowball across several debts."""

from __future__ import annotations

import argparse
from typing import List

from .. import argtypes
from ..core.dates import add_periods
from ..core.money import ZERO, dec, fmt_money, fmt_years
from ..core.payoff import STRATEGIES, Debt, simulate
from ..core.rates import Frequency
from ..loaders import (
    DataFileError,
    load_records,
    parse_amount,
    parse_rate,
    pick,
    require_columns,
)
from ..output import Report, emit
from ._common import add_as_of, add_output_args, today

NAME = "debt-plan"
HELP = "Order several debts by avalanche or snowball and compare the outcomes"

FILE_HELP = """\
CSV or JSON describing your debts. Recognised columns:
  name       label for the debt (required)
  balance    amount owed (required)
  rate       annual interest rate, e.g. 18.9, 18.9% or 0.189 (required)
  minimum    contractual minimum payment (required)
  priority   optional integer, used by --strategy custom

Example debts.csv:
  name,balance,rate,minimum
  Visa,5400,22.9,135
  Car loan,14200,4.9,318
"""


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        aliases=["debts"],
        help=HELP,
        description=(
            "Simulates paying every debt's minimum while directing all spare cash at "
            "one target at a time, rolling each cleared debt's minimum into the next. "
            "Reports both avalanche (highest rate first) and snowball (smallest "
            "balance first) so the real cost of the motivational choice is visible."
        ),
        epilog=FILE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", metavar="PATH", help="CSV or JSON file of debts")
    source.add_argument(
        "--debt",
        action="append",
        metavar="NAME:BALANCE:RATE:MINIMUM",
        help="describe a debt inline; repeatable",
    )
    parser.add_argument("--strategy", choices=STRATEGIES, default="avalanche",
                        help="which ordering to report as the plan")
    parser.add_argument("--extra", type=argtypes.nonneg_amount, default=ZERO,
                        help="spare cash available each period beyond the minimums")
    parser.add_argument("--frequency", type=argtypes.frequency, default=Frequency.MONTHLY,
                        help="how often payments are made")
    add_as_of(parser)
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def parse_inline(specs: List[str]) -> List[Debt]:
    debts = []
    for spec in specs:
        parts = spec.split(":")
        if len(parts) != 4:
            raise SystemExit(
                f"--debt expects NAME:BALANCE:RATE:MINIMUM, got {spec!r}"
            )
        name, balance, rate, minimum = (p.strip() for p in parts)
        try:
            rate_value = dec(rate.rstrip("%"))
        except ArithmeticError:
            raise SystemExit(f"--debt {spec!r}: {rate!r} is not a valid rate")
        debts.append(
            Debt(
                name=name,
                balance=parse_amount(balance, where=f"--debt {name}", field="balance"),
                annual_rate=rate_value / 100 if rate_value > 1 else rate_value,
                minimum=parse_amount(minimum, where=f"--debt {name}", field="minimum"),
            )
        )
    return debts


def load_debts(path: str) -> List[Debt]:
    records = load_records(path)
    require_columns(
        records,
        [("name", "debt", "label"), ("balance", "amount"), ("rate", "interest_rate", "apr"),
         ("minimum", "minimum_payment", "min_payment", "payment")],
        path,
    )
    debts = []
    for record in records:
        where = record.get("_where", path)
        name = str(pick(record, "name", "debt", "label") or "").strip()
        if not name:
            raise DataFileError(f"{where}: name is required")
        priority = pick(record, "priority", "order")
        debts.append(
            Debt(
                name=name,
                balance=parse_amount(pick(record, "balance", "amount"), where=where, field="balance"),
                annual_rate=parse_rate(
                    pick(record, "rate", "interest_rate", "apr"), where=where, field="rate"
                ),
                minimum=parse_amount(
                    pick(record, "minimum", "minimum_payment", "min_payment", "payment"),
                    where=where, field="minimum",
                ),
                priority=int(priority) if priority not in (None, "") else None,
            )
        )
    return debts


def run(args) -> int:
    debts = load_debts(args.file) if args.file else parse_inline(args.debt)
    outstanding = [d for d in debts if d.balance > 0]
    if not outstanding:
        print("Every listed debt already has a zero balance. Nothing to plan.")
        return 0

    freq = args.frequency
    start = today(args)
    plans = {name: simulate(outstanding, name, args.extra, freq) for name in ("avalanche", "snowball")}
    if args.strategy == "custom":
        plans["custom"] = simulate(outstanding, "custom", args.extra, freq)
    chosen = plans[args.strategy]
    minimums = sum((d.minimum for d in outstanding), ZERO)

    report = Report(
        f"Debt plan: {len(outstanding)} debts totalling {fmt_money(chosen.starting_balance)}",
        f"Strategy: {args.strategy} - {_describe(args.strategy)}",
    )
    report.money("Minimum payments", minimums)
    report.money("Extra each period", args.extra)
    report.money("Total budget", minimums + args.extra)
    report.add("Payments to debt-free", chosen.periods)
    report.add("Time to debt-free", fmt_years(chosen.periods, freq.per_year))
    report.add("Debt-free on", add_periods(start, chosen.periods - 1, freq))
    report.money("Total interest", chosen.total_interest)
    report.money("Total repaid", chosen.total_paid)

    report.section("Strategy comparison")
    best = min(plans.values(), key=lambda p: (p.total_interest, p.periods))
    for name, plan in plans.items():
        marker = "  <- cheapest" if plan is best else ""
        report.add(
            name.capitalize(),
            f"{plan.periods} payments, {fmt_money(plan.total_interest)} interest{marker}",
        )
    spread = max(p.total_interest for p in plans.values()) - best.total_interest
    if spread > 0:
        report.note(
            f"Choosing {best.strategy} over the most expensive ordering saves "
            f"{fmt_money(spread)} in interest."
        )
    if plans["snowball"].total_interest > plans["avalanche"].total_interest:
        first_snowball = plans["snowball"].per_debt[0]
        report.note(
            f"Snowball costs {fmt_money(plans['snowball'].total_interest - plans['avalanche'].total_interest)} "
            f"more but clears '{first_snowball.name}' in {first_snowball.periods_to_payoff} payments, "
            "which some people need to stay with the plan."
        )

    report.table(
        "Payoff order",
        ["#", "Debt", "Balance", "Rate", "Minimum payment", "Cleared after", "Interest paid"],
        [
            [
                index,
                result.name,
                result.starting_balance,
                f"{next(d.annual_rate for d in outstanding if d.name == result.name) * 100:.2f}%",
                next(d.minimum for d in outstanding if d.name == result.name),
                result.periods_to_payoff,
                result.interest_paid,
            ]
            for index, result in enumerate(chosen.per_debt, start=1)
        ],
    )
    report.table(
        "Period-by-period",
        ["Period", "Date", "Target", "Paid", "Interest", "Remaining balance"],
        [
            [
                row["period"],
                add_periods(start, int(row["period"]) - 1, freq),
                row["target"] or "-",
                row["paid"],
                row["interest"],
                row["remaining_balance"],
            ]
            for row in chosen.timeline
        ],
        preview_rows=18,
    )
    emit(report, args)
    return 0


def _describe(strategy: str) -> str:
    return {
        "avalanche": "highest interest rate first, which minimises total interest",
        "snowball": "smallest balance first, which clears individual debts fastest",
        "custom": "your own order from the 'priority' column",
    }[strategy]
