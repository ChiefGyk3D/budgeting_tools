"""``finplan mortgage`` -- amortisation schedules for any instalment loan."""

from __future__ import annotations

import argparse

from .. import argtypes
from ..core.amortization import (
    LoanTerms,
    amortize,
    compare_payoff,
    interest_paid_between,
)
from ..core.dates import periods_elapsed
from ..core.money import ZERO, fmt_money, fmt_years
from ..core.rates import Frequency
from ..core.tvm import NeverAmortizes
from ..output import Report, emit
from ._common import add_as_of, add_output_args, freq_adverb, parse_lump_sums, today

NAME = "mortgage"
ALIASES = ("loan", "amortize")
HELP = "Amortisation schedule, payoff date and extra-payment savings for a loan"


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        aliases=list(ALIASES),
        help=HELP,
        description=(
            "Builds a complete amortisation schedule for a mortgage, auto loan or any "
            "other level-payment instalment loan, and reports what extra payments save."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    loan = parser.add_argument_group("loan")
    loan.add_argument(
        "--balance",
        type=argtypes.positive_amount,
        required=True,
        help="principal still owed today",
    )
    loan.add_argument(
        "--original-principal",
        type=argtypes.positive_amount,
        help="original loan amount; defaults to --balance. Used to derive the "
        "contractual payment and the PMI loan-to-value test",
    )
    loan.add_argument("--rate", type=argtypes.percentage, required=True,
                      help="annual interest rate as a percentage, e.g. 6.5")
    loan.add_argument("--term", type=argtypes.years, required=True,
                      help="original term of the loan in years")
    loan.add_argument(
        "--start-date", "--first-payment", dest="start_date",
        type=argtypes.date, required=True, metavar="YYYY-MM-DD",
        help="date of the NEXT payment due on --balance. For a loan you are "
             "already part-way through, this is the upcoming payment date, not "
             "the origination date -- pass that as --origination-date",
    )
    loan.add_argument(
        "--origination-date", type=argtypes.date, metavar="YYYY-MM-DD",
        help="when the loan started; used only to report progress so far",
    )
    loan.add_argument(
        "--frequency",
        type=argtypes.frequency,
        default=Frequency.MONTHLY,
        help="monthly, biweekly, semimonthly, weekly, quarterly or annual. "
        "'biweekly' means the accelerated product: half the monthly payment "
        "every two weeks, i.e. 13 monthly-equivalents a year",
    )
    loan.add_argument(
        "--payment",
        type=argtypes.positive_amount,
        help="override the computed principal-and-interest payment",
    )

    extras = parser.add_argument_group("acceleration")
    extras.add_argument("--extra-payment", type=argtypes.nonneg_amount, default=ZERO,
                        help="additional principal paid every period")
    extras.add_argument(
        "--lump-sum",
        action="append",
        metavar="N:AMOUNT",
        help="one-off extra principal at payment number N; repeatable",
    )

    carrying = parser.add_argument_group("carrying costs")
    carrying.add_argument("--escrow", type=argtypes.nonneg_amount, default=ZERO,
                          help="taxes and insurance collected each period (not applied to principal)")
    carrying.add_argument("--pmi", type=argtypes.nonneg_amount, default=ZERO,
                          help="mortgage insurance premium charged each period")
    carrying.add_argument("--property-value", type=argtypes.positive_amount,
                          help="value used for the PMI loan-to-value test; required with --pmi")
    carrying.add_argument("--pmi-ltv-cutoff", type=argtypes.percentage, default=None,
                          metavar="PCT", help="LTV at which PMI stops (default 80)")

    add_as_of(parser)
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def build_terms(args) -> LoanTerms:
    kwargs = dict(
        balance=args.balance,
        annual_rate=args.rate,
        term_years=args.term,
        start_date=args.start_date,
        freq=args.frequency,
        original_principal=args.original_principal or args.balance,
        payment_override=args.payment,
        extra_payment=args.extra_payment,
        escrow=args.escrow,
        pmi=args.pmi,
        property_value=args.property_value,
        lump_sums=parse_lump_sums(args.lump_sum),
    )
    if args.pmi_ltv_cutoff is not None:
        kwargs["pmi_ltv_cutoff"] = args.pmi_ltv_cutoff
    return LoanTerms(**kwargs)


def run(args) -> int:
    if args.pmi > 0 and not args.property_value:
        raise SystemExit("--pmi requires --property-value to know when the premium drops off")

    terms = build_terms(args)
    try:
        comparison = compare_payoff(terms)
    except NeverAmortizes as exc:
        raise SystemExit(f"This loan never amortises: {exc}")

    schedule = comparison.accelerated
    baseline = comparison.baseline
    as_of = today(args)
    per = freq_adverb(terms.freq)

    report = Report(
        f"Loan summary: {fmt_money(terms.balance)} at {args.rate * 100:.3f}% over {terms.term_years} years",
        f"{terms.freq.label.capitalize()} payments starting {terms.start_date.isoformat()}",
    )
    report.money(f"Scheduled payment ({per})", terms.scheduled_payment)
    if terms.extra_payment:
        report.money(f"Extra principal ({per})", terms.extra_payment)
    if terms.escrow:
        report.money(f"Escrow ({per})", terms.escrow)
    if terms.pmi:
        report.money(f"Mortgage insurance ({per})", terms.pmi)
    total_outlay = terms.scheduled_payment + terms.extra_payment + terms.escrow + terms.pmi
    if total_outlay != terms.scheduled_payment:
        report.money(f"Total outlay ({per})", total_outlay)

    report.section("Payoff")
    report.add("Payments remaining", schedule.payment_count)
    report.add("Time to payoff", fmt_years(schedule.payment_count, terms.freq.per_year))
    report.add("Payoff date", schedule.payoff_date)
    report.money("Total interest", schedule.total_interest)
    report.money("Total paid", schedule.total_paid)
    if schedule.total_pmi:
        report.money("Total mortgage insurance", schedule.total_pmi)
        report.add("PMI drops off", schedule.pmi_drops_at or "not within this schedule")

    if comparison.interest_saved > 0 or comparison.payments_saved:
        label = "biweekly payments" if terms.freq is Frequency.BIWEEKLY else "extra payments"
        report.section(f"Effect of {label}")
        report.add("Baseline payoff date", baseline.payoff_date)
        report.money("Baseline total interest", baseline.total_interest)
        report.money("Interest saved", comparison.interest_saved)
        report.add("Payments saved", comparison.payments_saved)
        report.add(
            "Time saved",
            f"{comparison.time_saved_days // 365} years, "
            f"{(comparison.time_saved_days % 365) // 30} months",
        )

    upcoming = schedule.next_payment(as_of)
    if upcoming:
        report.section(f"Next payment (as of {as_of.isoformat()})")
        report.add("Payment number", f"{upcoming.number} of {schedule.payment_count}")
        report.add("Due", upcoming.date)
        report.money("Principal", upcoming.principal + upcoming.extra)
        report.money("Interest", upcoming.interest)
        report.money("Balance after", upcoming.ending_balance)
    else:
        report.note(f"The loan is already paid off as of {as_of.isoformat()}.")

    interest_this_year = interest_paid_between(
        schedule, as_of.replace(month=1, day=1), as_of.replace(month=12, day=31)
    )
    if interest_this_year:
        report.section("Tax year")
        report.money(f"Interest charged in {as_of.year}", interest_this_year)

    if args.origination_date:
        if args.origination_date > terms.start_date:
            raise SystemExit(
                "--origination-date must be on or before --start-date "
                "(the next payment cannot precede the loan)"
            )
        made = periods_elapsed(args.origination_date, terms.start_date, terms.freq)
        # Replay the original contract to get the interest actually charged and
        # the balance the schedule expects, rather than estimating from the
        # payment count alone.
        contract = amortize(
            LoanTerms(
                balance=terms.original_principal,
                annual_rate=terms.annual_rate,
                term_years=terms.term_years,
                start_date=args.origination_date,
                freq=terms.freq,
                payment_override=terms.payment_override,
            )
        )
        history = contract.rows[:made]
        expected_balance = history[-1].ending_balance if history else terms.original_principal
        interest_so_far = history[-1].cumulative_interest if history else ZERO
        paid_down = terms.original_principal - terms.balance

        report.section("Progress so far")
        report.add("Loan originated", args.origination_date)
        report.add("Payments made", f"{made} of {contract.payment_count}")
        report.money("Original principal", terms.original_principal)
        report.money("Principal repaid", paid_down)
        report.percent(
            "Share of principal repaid",
            paid_down / terms.original_principal if terms.original_principal else ZERO,
        )
        report.money("Interest charged so far", interest_so_far, "on the contractual schedule")

        drift = terms.balance - expected_balance
        if abs(drift) > terms.scheduled_payment:
            report.money("Balance the contract predicts", expected_balance)
            if drift < 0:
                report.note(
                    f"Your balance is {fmt_money(-drift)} below the contractual schedule, "
                    "which is what extra principal payments look like."
                )
            else:
                report.warn(
                    f"Your balance is {fmt_money(drift)} above what {made} contractual "
                    "payments would leave. Check --balance, --rate, --term or "
                    "--origination-date; one of them does not match the others."
                )

    columns = [
        "Number", "Date", "Starting balance", "Payment", "Principal",
        "Interest", "Extra", "Escrow", "PMI", "Total outlay",
        "Ending balance", "Cumulative interest",
    ]
    report.table(
        "Amortisation schedule",
        columns,
        (
            [
                row.number, row.date, row.starting_balance, row.scheduled_payment,
                row.principal, row.interest, row.extra, row.escrow, row.pmi,
                row.total_outlay, row.ending_balance, row.cumulative_interest,
            ]
            for row in schedule.rows
        ),
        preview_rows=18,
    )
    report.table(
        "Annual summary",
        ["Year", "Payments", "Principal", "Interest", "Extra", "Escrow", "PMI", "Ending balance"],
        (
            [y["year"], y["payments"], y["principal"], y["interest"], y["extra"],
             y["escrow"], y["pmi"], y["ending_balance"]]
            for y in schedule.year_summaries()
        ),
    )

    if terms.original_principal != terms.balance:
        report.note(
            "Payment 1 is the next payment due on the balance you entered; the "
            "schedule does not replay payments already made."
        )
    emit(report, args)
    return 0
