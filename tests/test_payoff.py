from decimal import Decimal

import pytest

from finplan.core.money import ZERO
from finplan.core.payoff import Debt, order_debts, simulate
from finplan.core.rates import as_rate
from finplan.core.tvm import NeverAmortizes

DEBTS = [
    Debt("Visa", Decimal("5400"), as_rate("22.9"), Decimal("135")),
    Debt("Store card", Decimal("1180"), as_rate("26.99"), Decimal("40")),
    Debt("Car loan", Decimal("14200"), as_rate("4.9"), Decimal("318")),
    Debt("Student loan", Decimal("22400"), as_rate("6.8"), Decimal("265")),
]


def test_avalanche_orders_by_rate_and_snowball_by_balance():
    assert [d.name for d in order_debts(DEBTS, "avalanche")][0] == "Store card"
    assert [d.name for d in order_debts(DEBTS, "snowball")][0] == "Store card"
    assert [d.name for d in order_debts(DEBTS, "avalanche")] == [
        "Store card", "Visa", "Student loan", "Car loan"
    ]
    assert [d.name for d in order_debts(DEBTS, "snowball")] == [
        "Store card", "Visa", "Car loan", "Student loan"
    ]


def test_ordering_is_independent_of_input_order():
    assert order_debts(DEBTS, "avalanche") == order_debts(list(reversed(DEBTS)), "avalanche")


def test_custom_order_follows_the_priority_column():
    debts = [
        Debt("A", Decimal("1000"), as_rate(5), Decimal("50"), priority=2),
        Debt("B", Decimal("1000"), as_rate(5), Decimal("50"), priority=1),
    ]
    assert [d.name for d in order_debts(debts, "custom")] == ["B", "A"]


def test_avalanche_never_costs_more_interest_than_snowball():
    avalanche = simulate(DEBTS, "avalanche", extra=Decimal("400"))
    snowball = simulate(DEBTS, "snowball", extra=Decimal("400"))
    assert avalanche.total_interest <= snowball.total_interest
    assert avalanche.periods <= snowball.periods


def test_every_debt_is_cleared_and_totals_reconcile():
    plan = simulate(DEBTS, "avalanche", extra=Decimal("400"))
    assert all(d.periods_to_payoff is not None for d in plan.per_debt)
    assert plan.starting_balance == sum(d.balance for d in DEBTS)
    assert plan.total_paid == plan.starting_balance + plan.total_interest
    assert plan.timeline[-1]["remaining_balance"] == ZERO


def test_freed_minimums_roll_into_the_next_target():
    """The whole point of a snowball: paying more later without paying more."""
    plan = simulate(DEBTS, "avalanche", extra=Decimal("400"))
    budget = sum(d.minimum for d in DEBTS) + Decimal("400")
    # Every period except the last spends the full budget.
    assert all(row["paid"] == budget for row in plan.timeline[:-1])
    assert plan.timeline[-1]["paid"] <= budget


def test_extra_payments_shorten_the_plan():
    without = simulate(DEBTS, "avalanche")
    with_extra = simulate(DEBTS, "avalanche", extra=Decimal("500"))
    assert with_extra.periods < without.periods
    assert with_extra.total_interest < without.total_interest


def test_targets_are_paid_in_order():
    plan = simulate(DEBTS, "avalanche", extra=Decimal("400"))
    targets = [row["target"] for row in plan.timeline if row["target"]]
    seen = []
    for target in targets:
        if not seen or seen[-1] != target:
            seen.append(target)
    assert seen == [name for name in plan.order if name in seen]


def test_minimums_below_interest_raise_rather_than_hang():
    hopeless = [Debt("Card", Decimal("20000"), as_rate(29), Decimal("100"))]
    with pytest.raises(NeverAmortizes):
        simulate(hopeless, "avalanche")


def test_zero_balance_debts_are_ignored():
    plan = simulate([Debt("Paid off", ZERO, as_rate(10), Decimal("50"))], "avalanche")
    assert plan.per_debt == []
    assert plan.periods == 0


def test_debt_validation():
    with pytest.raises(ValueError, match="balance"):
        Debt("X", Decimal("-1"), as_rate(5), Decimal("10"))
    with pytest.raises(ValueError, match="interest rate"):
        Debt("X", Decimal("100"), Decimal("-0.1"), Decimal("10"))
    with pytest.raises(ValueError, match="minimum"):
        Debt("X", Decimal("100"), as_rate(5), Decimal("-1"))


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError, match="unknown strategy"):
        order_debts(DEBTS, "lottery")
