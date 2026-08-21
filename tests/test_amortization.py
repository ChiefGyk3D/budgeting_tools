import datetime as dt
from decimal import Decimal

import pytest

from finplan.core.amortization import (
    LoanTerms,
    amortize,
    balance_on,
    compare_payoff,
    interest_paid_between,
)
from finplan.core.money import ZERO, money
from finplan.core.rates import Frequency, as_rate
from finplan.core.tvm import NeverAmortizes

START = dt.date(2026, 1, 31)


def loan(**overrides) -> LoanTerms:
    kwargs = dict(
        balance=Decimal("300000"),
        annual_rate=as_rate(6),
        term_years=Decimal("30"),
        start_date=START,
    )
    kwargs.update(overrides)
    return LoanTerms(**kwargs)


def test_scheduled_payment_matches_the_textbook_figure():
    assert loan().scheduled_payment == Decimal("1798.65")


def test_schedule_finishes_in_the_contractual_number_of_payments():
    """Rounding the payment to cents used to leave a stub 361st row."""
    schedule = amortize(loan())
    assert schedule.payment_count == 360
    assert schedule.rows[-1].ending_balance == ZERO
    assert schedule.rows[-1].total_outlay > loan().scheduled_payment


def test_principal_repaid_equals_the_balance_exactly():
    schedule = amortize(loan())
    assert schedule.total_principal == Decimal("300000.00")
    assert sum(r.principal + r.extra for r in schedule.rows) == Decimal("300000.00")


def test_balance_decreases_monotonically_and_never_goes_negative():
    schedule = amortize(loan(extra_payment=Decimal("500")))
    balances = [r.ending_balance for r in schedule.rows]
    assert all(b >= 0 for b in balances)
    assert balances == sorted(balances, reverse=True)


def test_extra_payment_is_not_mutated_across_rows():
    """The original added the negative overshoot into extra_payment in-place,
    corrupting every subsequent row."""
    extra = Decimal("400")
    schedule = amortize(loan(extra_payment=extra))
    body = schedule.rows[:-1]
    assert all(row.extra == extra for row in body)
    assert schedule.rows[-1].extra <= extra


def test_month_end_start_date_produces_valid_dates():
    schedule = amortize(loan(start_date=dt.date(2026, 1, 31), term_years=Decimal("2")))
    assert schedule.rows[1].date == dt.date(2026, 2, 28)
    assert len({r.date for r in schedule.rows}) == schedule.payment_count


def test_schedule_covers_the_whole_term_not_just_the_past():
    """The original broke out of the loop at the first future payment, so
    --output wrote a truncated CSV."""
    schedule = amortize(loan())
    assert schedule.rows[-1].date.year == 2055
    assert schedule.payment_count == 360


def test_extra_payments_shorten_the_loan_and_cut_interest():
    comparison = compare_payoff(loan(extra_payment=Decimal("300")))
    assert comparison.payments_saved > 0
    assert comparison.interest_saved > 0
    assert comparison.accelerated.total_interest < comparison.baseline.total_interest
    assert comparison.accelerated.payoff_date < comparison.baseline.payoff_date


def test_biweekly_is_half_the_monthly_payment():
    """Accelerated biweekly: half the monthly payment, 26 times a year."""
    monthly = loan().scheduled_payment
    biweekly = loan(freq=Frequency.BIWEEKLY)
    assert biweekly.scheduled_payment == money(monthly / 2)
    comparison = compare_payoff(biweekly)
    # 13 monthly-equivalents a year retires a 30-year loan in roughly 24-26.
    assert 24 * 26 <= comparison.accelerated.payment_count <= 26 * 26
    assert comparison.interest_saved > 0


def test_lump_sum_is_applied_at_the_right_payment():
    schedule = amortize(loan(lump_sums={12: Decimal("10000")}))
    assert schedule.rows[11].extra == Decimal("10000.00")
    assert schedule.rows[10].extra == ZERO
    assert schedule.total_interest < amortize(loan()).total_interest


def test_non_amortising_payment_raises_instead_of_looping_forever():
    with pytest.raises(NeverAmortizes):
        amortize(loan(payment_override=Decimal("100")))


def test_interest_only_payment_is_rejected():
    interest_only = Decimal("300000") * as_rate(6) / 12
    with pytest.raises(NeverAmortizes):
        amortize(loan(payment_override=money(interest_only)))


def test_zero_interest_loan_amortises_evenly():
    schedule = amortize(loan(annual_rate=ZERO, term_years=Decimal("1"), balance=Decimal("12000")))
    assert schedule.payment_count == 12
    assert schedule.total_interest == ZERO
    assert all(r.principal == Decimal("1000.00") for r in schedule.rows)


def test_zero_balance_yields_an_empty_schedule():
    schedule = amortize(loan(balance=ZERO))
    assert schedule.rows == []
    assert schedule.payoff_date is None
    assert schedule.total_interest == ZERO


def test_pmi_is_charged_until_the_ltv_cutoff_then_stops():
    schedule = amortize(
        loan(balance=Decimal("380000"), pmi=Decimal("158"), property_value=Decimal("400000"))
    )
    assert schedule.rows[0].pmi == Decimal("158.00")
    assert schedule.rows[-1].pmi == ZERO
    drop = schedule.pmi_drops_at
    assert drop is not None
    dropped_row = next(r for r in schedule.rows if r.date == drop)
    assert dropped_row.starting_balance / Decimal("400000") <= Decimal("0.80")
    assert all(r.pmi == ZERO for r in schedule.rows if r.date >= drop)


def test_escrow_is_not_applied_to_principal():
    with_escrow = amortize(loan(escrow=Decimal("500")))
    without = amortize(loan())
    assert with_escrow.payment_count == without.payment_count
    assert with_escrow.total_principal == without.total_principal
    assert with_escrow.total_paid == without.total_paid + Decimal("500") * without.payment_count


def test_cumulative_totals_are_consistent():
    schedule = amortize(loan(extra_payment=Decimal("200")))
    running = ZERO
    for row in schedule.rows:
        running += row.interest
        assert row.cumulative_interest == running
    assert schedule.total_interest == running


def test_year_summaries_partition_the_schedule():
    schedule = amortize(loan())
    summaries = schedule.year_summaries()
    assert sum(y["payments"] for y in summaries) == schedule.payment_count
    assert sum(y["interest"] for y in summaries) == schedule.total_interest
    assert [y["year"] for y in summaries] == sorted(y["year"] for y in summaries)


def test_interest_paid_between_matches_a_year_summary():
    schedule = amortize(loan())
    charged = interest_paid_between(schedule, dt.date(2027, 1, 1), dt.date(2027, 12, 31))
    from_summary = next(y for y in schedule.year_summaries() if y["year"] == 2027)["interest"]
    assert charged == from_summary


def test_balance_on_a_date():
    schedule = amortize(loan())
    assert balance_on(schedule, dt.date(2025, 1, 1)) == Decimal("300000.00")
    assert balance_on(schedule, schedule.rows[0].date) == schedule.rows[0].ending_balance
    assert balance_on(schedule, dt.date(2060, 1, 1)) == ZERO


def test_terms_reject_impossible_inputs():
    with pytest.raises(ValueError, match="balance"):
        loan(balance=Decimal("-1"))
    with pytest.raises(ValueError, match="term"):
        loan(term_years=Decimal("0"))
    with pytest.raises(ValueError, match="rate"):
        loan(annual_rate=Decimal("-0.01"))


def test_schedule_is_generated_in_one_pass():
    """Guards against reintroducing the O(n^2) payoff-date recomputation."""
    calls = {"n": 0}
    original = LoanTerms.scheduled_payment.fget

    def counting(self):
        calls["n"] += 1
        return original(self)

    LoanTerms.scheduled_payment = property(counting)
    try:
        amortize(loan())
    finally:
        LoanTerms.scheduled_payment = property(original)
    assert calls["n"] == 1
