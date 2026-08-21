from decimal import Decimal

import pytest

from finplan.core.money import money
from finplan.core.tvm import (
    NeverAmortizes,
    annuity_factor,
    contribution_for_goal,
    future_value,
    payment,
    periods_to_payoff,
    present_value,
    solve_rate,
)


def test_payment_matches_published_mortgage_figure():
    # $300,000 at 6% nominal over 360 months is the textbook $1,798.65.
    assert money(payment(Decimal("0.005"), 360, 300000)) == Decimal("1798.65")


def test_zero_rate_is_the_limit_not_a_division_by_zero():
    assert annuity_factor(0, 10) == 10
    assert money(payment(0, 12, 12000)) == Decimal("1000.00")
    assert future_value(0, 10, 100, 50) == 1050


def test_annuity_due_earns_one_extra_period():
    ordinary = future_value(Decimal("0.01"), 12, 100)
    due = future_value(Decimal("0.01"), 12, 100, due=True)
    assert due == ordinary * Decimal("1.01")


def test_future_value_and_present_value_invert():
    rate, nper, pmt = Decimal("0.004"), 120, Decimal("500")
    fv = future_value(rate, nper, pmt)
    assert present_value(rate, nper, pmt) == pytest.approx(
        fv / (1 + rate) ** nper, abs=Decimal("1e-15")
    )


def test_periods_to_payoff_agrees_with_payment():
    rate, nper, pv = Decimal("0.005"), 360, Decimal("300000")
    pmt = payment(rate, nper, pv)
    assert periods_to_payoff(rate, pmt, pv) == pytest.approx(360, abs=Decimal("1e-9"))


def test_periods_to_payoff_raises_instead_of_math_domain_error():
    """The bug in debt_calculator.py: math.log of a negative number."""
    with pytest.raises(NeverAmortizes) as info:
        periods_to_payoff(Decimal("0.005"), Decimal("100"), Decimal("300000"))
    assert "does not cover" in str(info.value)
    assert info.value.interest == Decimal("1500.000")


def test_periods_to_payoff_handles_zero_rate_and_cleared_balance():
    assert periods_to_payoff(0, 100, 1000) == 10
    assert periods_to_payoff(Decimal("0.01"), 100, 0) == 0


def test_contribution_for_goal_round_trips_through_future_value():
    rate, nper, goal, pv = Decimal("0.005"), 360, Decimal("1000000"), Decimal("50000")
    contribution = contribution_for_goal(rate, nper, goal, pv)
    assert future_value(rate, nper, contribution, pv) == pytest.approx(
        goal, abs=Decimal("1e-10")
    )


def test_contribution_for_goal_is_negative_when_already_on_track():
    """retirement_calculator.py printed this as an instruction to save a negative amount."""
    assert contribution_for_goal(Decimal("0.005"), 120, 1000, 100000) < 0


def test_contribution_for_goal_rejects_zero_horizon():
    with pytest.raises(ValueError, match="horizon"):
        contribution_for_goal(Decimal("0.005"), 0, 1000)


def test_solve_rate_recovers_a_known_rate():
    rate = Decimal("0.005")
    fv = future_value(rate, 120, 500, 30000)
    assert solve_rate(120, 500, 30000, fv) == pytest.approx(rate, abs=Decimal("1e-10"))


def test_solve_rate_returns_none_when_unbracketed():
    assert solve_rate(12, 100, 100, Decimal("-1e9")) is None
