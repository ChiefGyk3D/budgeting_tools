"""Loan amortisation engine.

One engine backs every loan-shaped command (mortgage, auto loan, student loan,
generic debt payoff).  It produces a complete schedule in a single pass -- the
original mortgage script recomputed the payoff date from scratch inside the
per-payment loop, which made a 360-row schedule do ~65,000 iterations of work.

Features the original lacked: month-end-safe dates, immutable extra payments,
one-off lump sums, escrow and PMI tracking with automatic PMI termination, a
correct final payment (no negative last row), and a hard iteration cap so a
non-amortising payment raises instead of looping forever.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Dict, List, Mapping, Optional

from .dates import add_periods
from .money import ZERO, dec, money
from .rates import Frequency, periodic_rate
from .tvm import NeverAmortizes, payment as level_payment

#: Refuse to build a schedule longer than a century of payments.  Any input
#: that gets this far is pathological, and an exception beats a hung process.
MAX_PERIODS = 100 * 52


@dataclass(frozen=True)
class LoanTerms:
    """Everything needed to build a schedule.

    ``balance`` is what is owed *today*; ``original_principal`` is only used to
    derive the scheduled payment and the PMI loan-to-value test, so a loan that
    is already part-way through its term is described accurately.
    """

    balance: Decimal
    annual_rate: Decimal
    term_years: Decimal
    start_date: _dt.date
    freq: Frequency = Frequency.MONTHLY
    original_principal: Optional[Decimal] = None
    payment_override: Optional[Decimal] = None
    extra_payment: Decimal = ZERO
    escrow: Decimal = ZERO
    pmi: Decimal = ZERO
    property_value: Optional[Decimal] = None
    pmi_ltv_cutoff: Decimal = dec("0.80")
    lump_sums: Mapping[int, Decimal] = field(default_factory=dict)
    final_payment_absorbs_residual: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "balance", dec(self.balance))
        object.__setattr__(self, "annual_rate", dec(self.annual_rate))
        object.__setattr__(self, "term_years", dec(self.term_years))
        object.__setattr__(self, "extra_payment", dec(self.extra_payment))
        object.__setattr__(self, "escrow", dec(self.escrow))
        object.__setattr__(self, "pmi", dec(self.pmi))
        if self.original_principal is None:
            object.__setattr__(self, "original_principal", self.balance)
        else:
            object.__setattr__(self, "original_principal", dec(self.original_principal))
        if self.payment_override is not None:
            object.__setattr__(self, "payment_override", dec(self.payment_override))
        if self.property_value is not None:
            object.__setattr__(self, "property_value", dec(self.property_value))
        if self.balance < 0:
            raise ValueError("balance cannot be negative")
        if self.term_years <= 0:
            raise ValueError("term must be positive")
        if self.annual_rate < 0:
            raise ValueError("interest rate cannot be negative")

    @property
    def scheduled_periods(self) -> int:
        """Total periods in the original term."""
        return int((self.term_years * self.freq.per_year).to_integral_value("ROUND_HALF_UP"))

    @property
    def period_rate(self) -> Decimal:
        """Per-period interest rate (nominal annual rate / periods per year)."""
        return periodic_rate(self.annual_rate, self.freq)

    @property
    def scheduled_payment(self) -> Decimal:
        """The contractual payment, excluding extras, escrow and PMI.

        A biweekly schedule uses *half the monthly payment* every two weeks --
        the way accelerated-biweekly mortgage products actually work, yielding
        13 monthly-equivalents a year.  The original script re-amortised over
        ``26 * term`` periods instead, which produces a payment that is *lower*
        than half the monthly one and therefore shows no acceleration at all.
        """
        if self.payment_override is not None:
            return self.payment_override
        if self.freq is Frequency.BIWEEKLY:
            monthly = level_payment(
                periodic_rate(self.annual_rate, Frequency.MONTHLY),
                int((self.term_years * 12).to_integral_value("ROUND_HALF_UP")),
                self.original_principal,
            )
            return money(monthly / 2)
        return money(
            level_payment(self.period_rate, self.scheduled_periods, self.original_principal)
        )


@dataclass(frozen=True)
class Payment:
    """A single row of an amortisation schedule.  All amounts are in cents."""

    number: int
    date: _dt.date
    starting_balance: Decimal
    interest: Decimal
    principal: Decimal
    extra: Decimal
    escrow: Decimal
    pmi: Decimal
    ending_balance: Decimal
    cumulative_interest: Decimal
    cumulative_principal: Decimal

    @property
    def scheduled_payment(self) -> Decimal:
        """Contractual principal + interest for this row."""
        return self.interest + self.principal

    @property
    def total_outlay(self) -> Decimal:
        """Everything actually written on the cheque this period."""
        return self.interest + self.principal + self.extra + self.escrow + self.pmi

    def as_dict(self) -> Dict[str, object]:
        return {
            "number": self.number,
            "date": self.date.isoformat(),
            "starting_balance": self.starting_balance,
            "payment": self.scheduled_payment,
            "interest": self.interest,
            "principal": self.principal,
            "extra": self.extra,
            "escrow": self.escrow,
            "pmi": self.pmi,
            "total_outlay": self.total_outlay,
            "ending_balance": self.ending_balance,
            "cumulative_interest": self.cumulative_interest,
            "cumulative_principal": self.cumulative_principal,
        }


@dataclass(frozen=True)
class Schedule:
    """A fully built amortisation schedule plus its headline totals."""

    terms: LoanTerms
    rows: List[Payment]

    @property
    def payment_count(self) -> int:
        return len(self.rows)

    @property
    def payoff_date(self) -> Optional[_dt.date]:
        return self.rows[-1].date if self.rows else None

    @property
    def total_interest(self) -> Decimal:
        return self.rows[-1].cumulative_interest if self.rows else ZERO

    @property
    def total_principal(self) -> Decimal:
        return self.rows[-1].cumulative_principal if self.rows else ZERO

    @property
    def total_escrow(self) -> Decimal:
        return sum((r.escrow for r in self.rows), ZERO)

    @property
    def total_pmi(self) -> Decimal:
        return sum((r.pmi for r in self.rows), ZERO)

    @property
    def total_paid(self) -> Decimal:
        """Every dollar leaving the borrower's pocket over the schedule."""
        return self.total_principal + self.total_interest + self.total_escrow + self.total_pmi

    @property
    def pmi_drops_at(self) -> Optional[_dt.date]:
        """Date of the first payment on which PMI is no longer charged."""
        seen_pmi = False
        for row in self.rows:
            if row.pmi > 0:
                seen_pmi = True
            elif seen_pmi:
                return row.date
        return None

    def rows_from(self, on_or_after: _dt.date) -> List[Payment]:
        return [r for r in self.rows if r.date >= on_or_after]

    def next_payment(self, on_or_after: _dt.date) -> Optional[Payment]:
        for row in self.rows:
            if row.date >= on_or_after:
                return row
        return None

    def year_summaries(self) -> List[Dict[str, object]]:
        """Per-calendar-year totals, useful for tax and cash-flow planning."""
        out: Dict[int, Dict[str, object]] = {}
        for row in self.rows:
            bucket = out.setdefault(
                row.date.year,
                {
                    "year": row.date.year,
                    "payments": 0,
                    "interest": ZERO,
                    "principal": ZERO,
                    "extra": ZERO,
                    "escrow": ZERO,
                    "pmi": ZERO,
                    "ending_balance": ZERO,
                },
            )
            bucket["payments"] += 1
            bucket["interest"] += row.interest
            bucket["principal"] += row.principal
            bucket["extra"] += row.extra
            bucket["escrow"] += row.escrow
            bucket["pmi"] += row.pmi
            bucket["ending_balance"] = row.ending_balance
        return [out[year] for year in sorted(out)]


def amortize(terms: LoanTerms) -> Schedule:
    """Build the complete schedule for ``terms``.

    The whole schedule is generated -- not just the rows before today -- so
    ``--output`` writes a usable file.  The original stopped at the first
    future payment and silently wrote a truncated CSV.
    """
    balance = money(terms.balance)
    scheduled = terms.scheduled_payment
    rate = terms.period_rate
    extra = money(terms.extra_payment)
    escrow = money(terms.escrow)
    pmi_premium = money(terms.pmi)
    lump_sums = {int(k): money(v) for k, v in terms.lump_sums.items()}

    if balance == 0:
        return Schedule(terms=terms, rows=[])

    first_interest = money(balance * rate)
    if scheduled + extra <= first_interest and not lump_sums:
        raise NeverAmortizes(scheduled + extra, first_interest)

    rows: List[Payment] = []
    cumulative_interest = ZERO
    cumulative_principal = ZERO
    number = 0

    while balance > 0:
        number += 1
        if number > MAX_PERIODS:
            raise NeverAmortizes(scheduled + extra, money(balance * rate))

        starting = balance
        interest = money(balance * rate)

        # PMI is charged while the loan-to-value ratio is above the cutoff and
        # is assessed on the balance at the *start* of the period.
        pmi = ZERO
        if pmi_premium > 0 and terms.property_value:
            if starting / terms.property_value > terms.pmi_ltv_cutoff:
                pmi = pmi_premium

        principal = scheduled - interest
        this_extra = extra + lump_sums.get(number, ZERO)

        # Rounding the level payment to whole cents leaves the loan a dollar or
        # two short at the end of its contractual term.  Lenders adjust the
        # final payment to clear it; without this the schedule grows a stub
        # 361st row for a 30-year mortgage.
        residual = balance - principal - this_extra
        if (
            terms.final_payment_absorbs_residual
            and number >= terms.scheduled_periods
            and ZERO < residual <= scheduled
        ):
            principal = balance - this_extra

        # Final payment: never overpay, never emit a negative balance.
        if principal + this_extra >= balance:
            if principal >= balance:
                principal = balance
                this_extra = ZERO
            else:
                this_extra = balance - principal
            balance = ZERO
        else:
            balance = balance - principal - this_extra

        cumulative_interest += interest
        cumulative_principal += principal + this_extra

        rows.append(
            Payment(
                number=number,
                date=add_periods(terms.start_date, number - 1, terms.freq),
                starting_balance=starting,
                interest=interest,
                principal=money(principal),
                extra=money(this_extra),
                escrow=escrow,
                pmi=money(pmi),
                ending_balance=money(balance),
                cumulative_interest=money(cumulative_interest),
                cumulative_principal=money(cumulative_principal),
            )
        )

    return Schedule(terms=terms, rows=rows)


@dataclass(frozen=True)
class PayoffComparison:
    """Baseline schedule versus an accelerated one."""

    baseline: Schedule
    accelerated: Schedule

    @property
    def interest_saved(self) -> Decimal:
        return self.baseline.total_interest - self.accelerated.total_interest

    @property
    def payments_saved(self) -> int:
        return self.baseline.payment_count - self.accelerated.payment_count

    @property
    def time_saved_days(self) -> int:
        if not self.baseline.payoff_date or not self.accelerated.payoff_date:
            return 0
        return (self.baseline.payoff_date - self.accelerated.payoff_date).days


def compare_payoff(terms: LoanTerms) -> PayoffComparison:
    """Compare ``terms`` against the same loan with no extra payments.

    The baseline strips extras *and* lump sums but keeps the frequency, so an
    accelerated-biweekly schedule is still measured against monthly payments --
    which is the comparison a borrower actually cares about.
    """
    baseline_freq = Frequency.MONTHLY if terms.freq is Frequency.BIWEEKLY else terms.freq
    baseline = replace(
        terms,
        freq=baseline_freq,
        extra_payment=ZERO,
        lump_sums={},
        payment_override=None if terms.freq is Frequency.BIWEEKLY else terms.payment_override,
    )
    return PayoffComparison(baseline=amortize(baseline), accelerated=amortize(terms))


def interest_paid_between(schedule: Schedule, start: _dt.date, end: _dt.date) -> Decimal:
    """Interest charged on payments falling in ``[start, end]`` -- tax season."""
    return sum((r.interest for r in schedule.rows if start <= r.date <= end), ZERO)


def balance_on(schedule: Schedule, when: _dt.date) -> Decimal:
    """Balance after the last payment on or before ``when``."""
    balance = money(schedule.terms.balance)
    for row in schedule.rows:
        if row.date > when:
            break
        balance = row.ending_balance
    return balance
