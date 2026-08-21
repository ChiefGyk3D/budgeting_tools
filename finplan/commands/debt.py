"""``finplan debt`` -- payoff time and interest for a single balance."""

from __future__ import annotations

import argparse

from .. import argtypes
from ..core.amortization import LoanTerms, amortize
from ..core.money import ZERO, fmt_money, fmt_years, money
from ..core.rates import Frequency, periodic_rate
from ..core.tvm import NeverAmortizes, payment as level_payment, periods_to_payoff
from ..output import Report, emit
from ._common import add_as_of, add_output_args, freq_adverb, today

NAME = "debt"
HELP = "How long a balance takes to clear, and what paying more would save"


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        help=HELP,
        description=(
            "Given a balance, a rate and either a payment or a target payoff date, "
            "reports the payoff time, the total interest, and a sensitivity table "
            "showing what extra payments would save."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--balance", "--principal", dest="balance",
                        type=argtypes.positive_amount, required=True,
                        help="current balance owed")
    parser.add_argument("--rate", "--interest-rate", dest="rate",
                        type=argtypes.percentage, required=True,
                        help="annual interest rate as a percentage, e.g. 18.9")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--payment", "--monthly-payment", dest="payment",
                        type=argtypes.positive_amount,
                        help="amount paid each period")
    target.add_argument("--payoff-in", type=argtypes.positive_int, metavar="PERIODS",
                        help="solve for the payment that clears the balance in this many periods")
    parser.add_argument("--extra", type=argtypes.nonneg_amount, default=ZERO,
                        help="additional amount paid each period on top of --payment")
    parser.add_argument("--frequency", type=argtypes.frequency, default=Frequency.MONTHLY,
                        help="payment frequency")
    parser.add_argument("--start-date", type=argtypes.date, metavar="YYYY-MM-DD",
                        help="date of the next payment (default: today)")
    add_as_of(parser)
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def run(args) -> int:
    freq = args.frequency
    rate = periodic_rate(args.rate, freq)
    start = args.start_date or today(args)
    per = freq_adverb(freq)

    if args.payoff_in:
        payment = money(level_payment(rate, args.payoff_in, args.balance))
    else:
        payment = args.payment

    total_payment = payment + args.extra
    first_interest = money(args.balance * rate)
    if total_payment <= first_interest:
        raise SystemExit(
            f"A payment of {fmt_money(total_payment)} does not cover the "
            f"{fmt_money(first_interest)} of interest accruing each period. "
            f"You need to pay more than {fmt_money(first_interest)} to make progress."
        )

    # A term long enough that the level payment is never the binding constraint;
    # the schedule ends when the balance hits zero.
    horizon = periods_to_payoff(rate, total_payment, args.balance)
    term_years = max((horizon / freq.per_year) * 2, 1)
    terms = LoanTerms(
        balance=args.balance,
        annual_rate=args.rate,
        term_years=term_years,
        start_date=start,
        freq=freq,
        payment_override=payment,
        extra_payment=args.extra,
        final_payment_absorbs_residual=False,
    )
    schedule = amortize(terms)

    report = Report(
        f"Debt payoff: {fmt_money(args.balance)} at {args.rate * 100:.3f}%",
        f"{fmt_money(total_payment)} {per}, starting {start.isoformat()}",
    )
    if args.payoff_in:
        report.money(f"Required payment ({per})", payment)
    report.add("Payments to clear", schedule.payment_count)
    report.add("Time to clear", fmt_years(schedule.payment_count, freq.per_year))
    report.add("Debt-free on", schedule.payoff_date)
    report.money("Total interest", schedule.total_interest)
    report.money("Total repaid", schedule.total_paid)
    report.percent(
        "Interest as share of balance",
        schedule.total_interest / args.balance if args.balance else ZERO,
    )
    report.money("First payment goes to interest", first_interest)
    report.money("First payment goes to principal", total_payment - first_interest)

    rows = []
    for bump in (ZERO, money(25), money(50), money(100), money(250), money(500)):
        candidate = total_payment + bump
        try:
            trial = amortize(
                LoanTerms(
                    balance=args.balance,
                    annual_rate=args.rate,
                    term_years=term_years,
                    start_date=start,
                    freq=freq,
                    payment_override=candidate,
                    final_payment_absorbs_residual=False,
                )
            )
        except NeverAmortizes:
            continue
        rows.append(
            [
                candidate,
                trial.payment_count,
                trial.payoff_date,
                trial.total_interest,
                schedule.total_interest - trial.total_interest,
                schedule.payment_count - trial.payment_count,
            ]
        )
    report.table(
        "What paying more would do",
        ["Payment", "Periods", "Payoff date", "Total interest", "Interest saved", "Periods saved"],
        rows,
    )
    emit(report, args)
    return 0
