"""Multi-debt payoff simulation (avalanche / snowball / custom order).

Handles the part that makes these strategies work and that a spreadsheet
usually gets wrong: when a debt is cleared, its minimum payment *rolls into*
the next target rather than leaving the budget.  Both strategies are simulated
month by month against the same total budget so the comparison is honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Sequence

from .money import ZERO, Numeric, dec, money
from .rates import Frequency, periodic_rate
from .tvm import NeverAmortizes

MAX_PERIODS = 100 * 12

STRATEGIES = ("avalanche", "snowball", "custom")


@dataclass(frozen=True)
class Debt:
    """One borrowing line: balance, rate and contractual minimum payment."""

    name: str
    balance: Decimal
    annual_rate: Decimal
    minimum: Decimal
    priority: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "balance", money(self.balance))
        object.__setattr__(self, "annual_rate", dec(self.annual_rate))
        object.__setattr__(self, "minimum", money(self.minimum))
        if self.balance < 0:
            raise ValueError(f"{self.name}: balance cannot be negative")
        if self.annual_rate < 0:
            raise ValueError(f"{self.name}: interest rate cannot be negative")
        if self.minimum < 0:
            raise ValueError(f"{self.name}: minimum payment cannot be negative")


@dataclass
class DebtResult:
    """Per-debt outcome of a simulation."""

    name: str
    starting_balance: Decimal
    interest_paid: Decimal
    periods_to_payoff: Optional[int]

    @property
    def total_paid(self) -> Decimal:
        return self.starting_balance + self.interest_paid


@dataclass
class PayoffPlan:
    """The result of simulating one strategy."""

    strategy: str
    freq: Frequency
    order: List[str]
    per_debt: List[DebtResult]
    timeline: List[Dict[str, object]] = field(default_factory=list)

    @property
    def periods(self) -> int:
        return len(self.timeline)

    @property
    def total_interest(self) -> Decimal:
        return sum((d.interest_paid for d in self.per_debt), ZERO)

    @property
    def total_paid(self) -> Decimal:
        return sum((d.total_paid for d in self.per_debt), ZERO)

    @property
    def starting_balance(self) -> Decimal:
        return sum((d.starting_balance for d in self.per_debt), ZERO)


def order_debts(debts: Sequence[Debt], strategy: str) -> List[Debt]:
    """Target order for ``strategy``.

    Ties are broken by the other strategy's key so the ordering is stable and
    deterministic regardless of input order.
    """
    if strategy == "avalanche":
        return sorted(debts, key=lambda d: (-d.annual_rate, d.balance, d.name))
    if strategy == "snowball":
        return sorted(debts, key=lambda d: (d.balance, -d.annual_rate, d.name))
    if strategy == "custom":
        return sorted(
            debts,
            key=lambda d: (d.priority if d.priority is not None else 10**6, d.name),
        )
    raise ValueError(f"unknown strategy {strategy!r}; expected one of {', '.join(STRATEGIES)}")


def simulate(
    debts: Sequence[Debt],
    strategy: str = "avalanche",
    extra: Numeric = ZERO,
    freq: Frequency = Frequency.MONTHLY,
) -> PayoffPlan:
    """Pay minimums on everything and throw ``extra`` plus freed-up minimums at
    the current target until every balance is zero.
    """
    active = [d for d in debts if d.balance > 0]
    if not active:
        return PayoffPlan(strategy=strategy, freq=freq, order=[], per_debt=[])

    sequence = order_debts(active, strategy)
    budget = sum((d.minimum for d in active), ZERO) + money(extra)

    balances = {d.name: d.balance for d in active}
    interest_paid = {d.name: ZERO for d in active}
    payoff_period: Dict[str, Optional[int]] = {d.name: None for d in active}
    rates = {d.name: periodic_rate(d.annual_rate, freq) for d in active}
    minimums = {d.name: d.minimum for d in active}

    timeline: List[Dict[str, object]] = []
    period = 0

    while any(balances[name] > 0 for name in balances):
        period += 1
        if period > MAX_PERIODS:
            outstanding = [n for n in balances if balances[n] > 0]
            accruing = sum((balances[n] * rates[n] for n in outstanding), ZERO)
            raise NeverAmortizes(budget, money(accruing))

        # 1. Accrue interest on every outstanding balance.
        period_interest = ZERO
        for name in balances:
            if balances[name] <= 0:
                continue
            charge = money(balances[name] * rates[name])
            balances[name] += charge
            interest_paid[name] += charge
            period_interest += charge

        # 2. Pay the contractual minimum on every debt (never more than owed).
        available = budget
        paid_this_period: Dict[str, Decimal] = {}
        for debt in sequence:
            name = debt.name
            if balances[name] <= 0:
                continue
            pay = min(minimums[name], balances[name], available)
            balances[name] -= pay
            available -= pay
            paid_this_period[name] = pay

        # 3. Everything left over -- the extra plus the minimums of debts
        #    already cleared -- goes to the current target, in order.
        for debt in sequence:
            if available <= 0:
                break
            name = debt.name
            if balances[name] <= 0:
                continue
            pay = min(available, balances[name])
            balances[name] -= pay
            available -= pay
            paid_this_period[name] = paid_this_period.get(name, ZERO) + pay

        if not paid_this_period:
            raise NeverAmortizes(budget, money(period_interest))
        if all(v == 0 for v in paid_this_period.values()):
            raise NeverAmortizes(budget, money(period_interest))

        for name in balances:
            if balances[name] <= 0 and payoff_period[name] is None:
                payoff_period[name] = period

        target = next((d.name for d in sequence if balances[d.name] > 0), None)
        timeline.append(
            {
                "period": period,
                "target": target,
                "paid": money(budget - available),
                "interest": money(period_interest),
                "remaining_balance": money(sum(balances.values(), ZERO)),
                "balances": {n: money(b) for n, b in balances.items()},
            }
        )

    starting = {d.name: d.balance for d in active}
    return PayoffPlan(
        strategy=strategy,
        freq=freq,
        order=[d.name for d in sequence],
        per_debt=[
            DebtResult(
                name=d.name,
                starting_balance=starting[d.name],
                interest_paid=money(interest_paid[d.name]),
                periods_to_payoff=payoff_period[d.name],
            )
            for d in sequence
        ],
        timeline=timeline,
    )
