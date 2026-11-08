"""Time-value-of-money primitives.

Closed-form annuity formulas, all sign-consistent and all guarded against the
degenerate cases the original scripts crashed on: a zero interest rate (which
makes the annuity factor 0/0) and a payment too small to cover the periodic
interest (which makes the ``nper`` logarithm undefined).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from .money import ONE, ZERO, Numeric, dec


class NeverAmortizes(ValueError):
    """Raised when a payment can never retire the balance.

    ``debt_calculator.py`` hit this case as a bare ``ValueError: math domain
    error`` from ``math.log``.  Naming it lets callers report the actual
    financial problem: the payment is below the interest accruing each period.
    """

    def __init__(self, payment: Decimal, interest: Decimal) -> None:
        self.payment = payment
        self.interest = interest
        shortfall = interest - payment
        super().__init__(
            f"a payment of {payment} does not cover the {interest} of interest "
            f"accruing each period; the balance grows by {shortfall} per period "
            f"and is never repaid"
        )


def annuity_factor(rate: Numeric, nper: int) -> Decimal:
    """Present-value factor of an ordinary annuity of 1 per period.

    ``(1 - (1 + r)^-n) / r``, with the ``r == 0`` limit of ``n`` handled
    explicitly instead of dividing by zero.
    """
    r = dec(rate)
    if nper < 0:
        raise ValueError("nper must be non-negative")
    if r == 0:
        return dec(nper)
    return (ONE - (ONE + r) ** -nper) / r


def future_value(
    rate: Numeric,
    nper: int,
    pmt: Numeric = ZERO,
    pv: Numeric = ZERO,
    *,
    due: bool = False,
) -> Decimal:
    """Value after ``nper`` periods of ``pv`` plus ``pmt`` contributed each period.

    ``due=True`` contributes at the *start* of each period (annuity due), which
    is how payroll deferrals and most automatic transfers actually behave and
    is worth one extra period of growth.
    """
    r, p, v = dec(rate), dec(pmt), dec(pv)
    if nper < 0:
        raise ValueError("nper must be non-negative")
    if r == 0:
        return v + p * nper
    growth = (ONE + r) ** nper
    fv_annuity = p * (growth - ONE) / r
    if due:
        fv_annuity *= ONE + r
    return v * growth + fv_annuity


def present_value(
    rate: Numeric,
    nper: int,
    pmt: Numeric = ZERO,
    fv: Numeric = ZERO,
    *,
    due: bool = False,
) -> Decimal:
    """Present value of an annuity of ``pmt`` plus a lump sum ``fv``."""
    r = dec(rate)
    factor = annuity_factor(r, nper)
    if due:
        factor *= ONE + r
    discount = ONE if r == 0 else (ONE + r) ** -nper
    return dec(pmt) * factor + dec(fv) * discount


def payment(
    rate: Numeric,
    nper: int,
    pv: Numeric,
    fv: Numeric = ZERO,
    *,
    due: bool = False,
) -> Decimal:
    """Level payment that amortises ``pv`` to ``fv`` over ``nper`` periods."""
    if nper <= 0:
        raise ValueError("nper must be positive")
    r = dec(rate)
    factor = annuity_factor(r, nper)
    if due:
        factor *= ONE + r
    discount = ONE if r == 0 else (ONE + r) ** -nper
    return (dec(pv) - dec(fv) * discount) / factor


def periods_to_payoff(rate: Numeric, pmt: Numeric, pv: Numeric) -> Decimal:
    """Number of payments of ``pmt`` needed to clear a balance of ``pv``.

    Returns a fractional count; callers round up for a payment count and can
    use the fraction to size the final payment.  Raises :class:`NeverAmortizes`
    rather than producing a domain error.
    """
    r, p, v = dec(rate), dec(pmt), dec(pv)
    if v <= 0:
        return ZERO
    if p <= 0:
        raise NeverAmortizes(p, v * r)
    if r == 0:
        return v / p
    interest = v * r
    if p <= interest:
        raise NeverAmortizes(p, interest)
    return -((ONE - interest / p).ln()) / (ONE + r).ln()


def contribution_for_goal(
    rate: Numeric,
    nper: int,
    goal: Numeric,
    pv: Numeric = ZERO,
    *,
    due: bool = False,
) -> Decimal:
    """Per-period contribution needed to grow ``pv`` to ``goal`` in ``nper``.

    A negative result means the existing balance already overshoots the goal
    on its own; callers should surface that as "you are ahead of schedule"
    rather than instructing the user to save a negative amount.
    """
    if nper <= 0:
        raise ValueError("nper must be positive; check that the horizon is not zero")
    r = dec(rate)
    shortfall = dec(goal) - future_value(r, nper, ZERO, pv)
    if r == 0:
        divisor = dec(nper)
    else:
        divisor = ((ONE + r) ** nper - ONE) / r
        if due:
            divisor *= ONE + r
    return shortfall / divisor


def solve_rate(
    nper: int,
    pmt: Numeric,
    pv: Numeric,
    fv: Numeric = ZERO,
    *,
    guess: Numeric = "0.01",
    tolerance: Numeric = "1e-12",
    max_iterations: int = 200,
) -> Optional[Decimal]:
    """Per-period rate implied by a cash-flow set, by bisection.

    Bisection rather than Newton: it cannot diverge, and the bracket
    ``(-0.999, 10)`` per period covers every realistic loan or investment.
    Returns ``None`` if no sign change exists in the bracket.
    """
    tol = dec(tolerance)

    def balance(rate: Decimal) -> Decimal:
        return future_value(rate, nper, pmt, pv) - dec(fv)

    lo, hi = dec("-0.999"), dec("10")
    f_lo, f_hi = balance(lo), balance(hi)
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if (f_lo > 0) == (f_hi > 0):
        return None
    for _ in range(max_iterations):
        mid = (lo + hi) / 2
        f_mid = balance(mid)
        if f_mid == 0 or (hi - lo) / 2 < tol:
            return mid
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return (lo + hi) / 2
