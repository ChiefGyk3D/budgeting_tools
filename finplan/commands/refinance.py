"""``finplan refinance`` -- is the new rate worth the closing costs?"""

from __future__ import annotations

import argparse

from .. import argtypes
from ..core.amortization import LoanTerms, amortize
from ..core.money import ZERO, fmt_money, fmt_years
from ..core.rates import Frequency
from ..output import Report, emit
from ._common import add_output_args

NAME = "refinance"
HELP = "Compare your current loan against a refinance, including break-even"


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        help=HELP,
        description=(
            "Compares the interest remaining on your current loan against a new one, "
            "and reports how many payments it takes for the lower payment to repay "
            "the closing costs."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    current = parser.add_argument_group("current loan")
    current.add_argument("--balance", type=argtypes.positive_amount, required=True,
                         help="principal still owed")
    current.add_argument("--rate", type=argtypes.percentage, required=True,
                         help="current annual rate as a percentage")
    current.add_argument("--remaining-term", type=argtypes.years, required=True,
                         help="years left on the current loan")
    current.add_argument("--payment", type=argtypes.positive_amount,
                         help="current principal-and-interest payment; computed if omitted")

    new = parser.add_argument_group("new loan")
    new.add_argument("--new-rate", type=argtypes.percentage, required=True,
                     help="new annual rate as a percentage")
    new.add_argument("--new-term", type=argtypes.years, required=True,
                     help="term of the new loan in years")
    new.add_argument("--closing-costs", type=argtypes.nonneg_amount, default=ZERO,
                     help="origination, appraisal, title and other costs to close")
    new.add_argument("--roll-costs-in", action="store_true",
                     help="finance the closing costs instead of paying them at closing")
    new.add_argument("--start-date", type=argtypes.date, metavar="YYYY-MM-DD",
                     help="first payment date of the new loan (default: today)")

    parser.add_argument("--frequency", type=argtypes.frequency, default=Frequency.MONTHLY,
                        help="payment frequency for both loans")
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def run(args) -> int:
    import datetime as _dt

    freq = args.frequency
    start = args.start_date or _dt.date.today()

    current = amortize(
        LoanTerms(
            balance=args.balance,
            annual_rate=args.rate,
            term_years=args.remaining_term,
            start_date=start,
            freq=freq,
            payment_override=args.payment,
        )
    )
    new_principal = args.balance + (args.closing_costs if args.roll_costs_in else ZERO)
    new = amortize(
        LoanTerms(
            balance=new_principal,
            annual_rate=args.new_rate,
            term_years=args.new_term,
            start_date=start,
            freq=freq,
        )
    )

    current_payment = current.terms.scheduled_payment
    new_payment = new.terms.scheduled_payment
    payment_drop = current_payment - new_payment
    cash_at_closing = ZERO if args.roll_costs_in else args.closing_costs
    interest_saved = current.total_interest - new.total_interest
    net_saving = interest_saved - args.closing_costs

    report = Report(
        f"Refinance {fmt_money(args.balance)}: "
        f"{args.rate * 100:.3f}% -> {args.new_rate * 100:.3f}%",
        f"{args.remaining_term} years remaining vs a new {args.new_term}-year term",
    )
    report.money("Current payment", current_payment)
    report.money("New payment", new_payment)
    report.money("Change in payment", -payment_drop, "negative means cheaper")
    report.money("Closing costs", args.closing_costs)
    report.money("Cash needed at closing", cash_at_closing)
    if args.roll_costs_in and args.closing_costs:
        report.money("New loan amount", new_principal, "closing costs financed")

    report.section("Break-even")
    if payment_drop > 0:
        periods = int((args.closing_costs / payment_drop).to_integral_value("ROUND_CEILING"))
        report.add("Payments to recover costs", periods)
        report.add("Break-even after", fmt_years(periods, freq.per_year))
        if periods > new.payment_count:
            report.warn(
                "The lower payment never recovers the closing costs within the new term."
            )
    elif payment_drop == 0:
        report.add("Payments to recover costs", "n/a", "the payment does not change")
    else:
        report.add("Payments to recover costs", "never", "the new payment is higher")
        report.note(
            "A higher payment on a shorter term can still be the better deal - "
            "check 'Interest over the life of the loan' below."
        )

    report.section("Interest over the life of the loan")
    report.money("Current loan, interest remaining", current.total_interest)
    report.money("New loan, total interest", new.total_interest)
    report.money("Interest saved", interest_saved)
    report.money("Net saving after closing costs", net_saving)
    report.add("Current loan paid off", current.payoff_date)
    report.add("New loan paid off", new.payoff_date)

    if args.new_term > args.remaining_term:
        report.warn(
            f"The new term is {args.new_term - args.remaining_term} years longer. "
            "Even at a lower rate, restarting the clock can raise lifetime interest."
        )

    # The comparison that removes the term difference: take the new rate but keep
    # writing the old payment amount.
    if payment_drop > 0:
        keep_paying = amortize(
            LoanTerms(
                balance=new_principal,
                annual_rate=args.new_rate,
                term_years=args.new_term,
                start_date=start,
                freq=freq,
                payment_override=current_payment,
            )
        )
        report.section("If you refinance but keep paying the old amount")
        report.money("Payment", current_payment)
        report.add("Payments", keep_paying.payment_count)
        report.add("Paid off", keep_paying.payoff_date)
        report.money("Total interest", keep_paying.total_interest)
        report.money(
            "Saved vs current loan",
            current.total_interest - keep_paying.total_interest - args.closing_costs,
            "net of closing costs",
        )

    report.table(
        "Side by side",
        ["Metric", "Current loan", "New loan"],
        [
            ["Rate", f"{args.rate * 100:.3f}%", f"{args.new_rate * 100:.3f}%"],
            ["Payment", current_payment, new_payment],
            ["Payments remaining", current.payment_count, new.payment_count],
            ["Payoff date", current.payoff_date, new.payoff_date],
            ["Total interest", current.total_interest, new.total_interest],
            ["Total paid", current.total_paid, new.total_paid + cash_at_closing],
        ],
    )
    emit(report, args)
    return 0
