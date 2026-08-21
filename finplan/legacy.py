"""Compatibility shims for the original standalone scripts.

The scripts at the repository root still run, still take their old flags, and
now route through the fixed engine.  Each prints the equivalent ``finplan``
command to stderr so existing cron jobs and shell aliases keep working while
their owners migrate.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from typing import Callable, Dict, List, Optional

from .cli import main as cli_main


def _announce(argv: List[str], script: str) -> None:
    equivalent = "finplan " + " ".join(shlex.quote(a) for a in argv)
    print(
        f"note: {script} is a compatibility wrapper. The same run is:\n"
        f"  {equivalent}\n",
        file=sys.stderr,
    )


def _run(argv: List[str], script: str) -> int:
    _announce(argv, script)
    return cli_main(argv)


def biweekly_pay(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Months with three biweekly paychecks.")
    parser.add_argument("--pay-date", required=True, help="a known payday (YYYY-MM-DD)")
    parser.add_argument("--output", help="write the pay calendar to this CSV file")
    parser.add_argument("--year", type=int, help="calendar year to report on")
    known = parser.parse_args(args)

    argv = ["paychecks", "--first-payday", known.pay_date]
    if known.year:
        argv += ["--year", str(known.year)]
    if known.output:
        argv += ["--csv", known.output]
    return _run(argv, "biweekly_pay.py")


#: The original budget_planner.py flags, mapped to category names.  Every one
#: was ``required=True``; they are all optional now and default to zero.
BUDGET_CATEGORIES: Dict[str, str] = {
    "investments": "Investments",
    "rainy_day": "Rainy day fund",
    "work_gas": "Commuting fuel",
    "student_loans": "Student loans",
    "alarm": "Home alarm",
    "dog_insurance": "Pet insurance",
    "car_insurance": "Car insurance",
    "internet": "Internet",
    "gas": "Gas bill",
    "electric": "Electric",
    "water": "Water",
    "cell_phone": "Cell phone",
    "mortgage": "Mortgage",
    "house_insurance": "Home insurance",
    "life_insurance": "Life insurance",
    "property_taxes": "Property taxes",
    "other": "Other",
}


def budget_planner(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Monthly budget remainder.")
    parser.add_argument("--income", type=float, required=True, help="Monthly income")
    for flag in BUDGET_CATEGORIES:
        parser.add_argument(
            f"--{flag}", type=float, default=0.0, help=f"Monthly {flag.replace('_', ' ')}"
        )
    known = parser.parse_args(args)

    argv = ["budget", "--income", repr(known.income)]
    for flag, label in BUDGET_CATEGORIES.items():
        value = getattr(known, flag)
        if value:
            argv += ["--category", f"{label}={value!r}"]
    if len(argv) == 3:
        print(
            "error: give at least one spending category, e.g. --mortgage 1850",
            file=sys.stderr,
        )
        return 2
    return _run(argv, "budget_planner.py")


def debt_calculator(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Time to pay off a debt.")
    parser.add_argument("--principal", "--debt", dest="principal", type=float, required=True)
    parser.add_argument("--interest-rate", type=float, required=True)
    parser.add_argument("--monthly-payment", type=float, required=True)
    known = parser.parse_args(args)
    return _run(
        [
            "debt",
            "--balance", repr(known.principal),
            "--rate", repr(known.interest_rate),
            "--payment", repr(known.monthly_payment),
        ],
        "debt_calculator.py",
    )


def expense_tracker(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Record an expense.")
    parser.add_argument("--amount", type=float, required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--category", default="uncategorised")
    parser.add_argument("--recurring", action="store_true")
    parser.add_argument("--file", default="expenses.csv",
                        help="ledger file (the original always used ./expenses.csv)")
    known = parser.parse_args(args)

    argv = [
        "expenses", "--file", known.file, "add",
        "--amount", repr(known.amount),
        "--description", known.description,
        "--category", known.category,
    ]
    if known.recurring:
        argv.append("--recurring")
    return _run(argv, "expense_tracker.py")


def investment_calculator(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Future value of an investment.")
    parser.add_argument("--initial-investment", type=float, required=True)
    parser.add_argument("--monthly-investment", type=float, required=True)
    parser.add_argument("--years", type=int, required=True)
    parser.add_argument("--interest-rate", type=float, required=True)
    known = parser.parse_args(args)
    return _run(
        [
            "invest",
            "--initial", repr(known.initial_investment),
            "--contribution", repr(known.monthly_investment),
            "--years", str(known.years),
            "--return", repr(known.interest_rate),
            # The original divided the annual rate by 12, i.e. the nominal
            # convention. Preserved here so the number does not move.
            "--nominal-rate",
        ],
        "investment_calculator.py",
    )


def mortgage_calculator(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mortgage amortisation schedule.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--remaining-principal", type=float, required=True)
    parser.add_argument("--original-principal", type=float, required=True)
    parser.add_argument("--interest-rate", type=float, required=True)
    parser.add_argument("--term", type=int, required=True)
    parser.add_argument("--extra-payment", type=float, default=0.0)
    parser.add_argument("--biweekly", action="store_true")
    parser.add_argument("--output", help="write the payment schedule to this CSV file")
    known = parser.parse_args(args)

    argv = [
        "mortgage",
        "--balance", repr(known.remaining_principal),
        "--original-principal", repr(known.original_principal),
        "--rate", repr(known.interest_rate),
        "--term", str(known.term),
        "--start-date", known.start_date,
    ]
    if known.extra_payment:
        argv += ["--extra-payment", repr(known.extra_payment)]
    if known.biweekly:
        argv += ["--frequency", "biweekly"]
    if known.output:
        argv += ["--csv", known.output]
    _announce(argv, "mortgage_calculator.py")
    print(
        "note: --start-date is now the date of the NEXT payment on "
        "--remaining-principal. Pass the origination date as --origination-date "
        "to see progress so far.\n",
        file=sys.stderr,
    )
    return cli_main(argv)


def retirement_calculator(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Monthly saving needed for retirement.")
    parser.add_argument("--current-age", type=int, required=True)
    parser.add_argument("--retirement-age", type=int, required=True)
    parser.add_argument("--current-savings", type=float, required=True)
    parser.add_argument("--retirement-savings", type=float, required=True)
    # The original defaulted to 0.05 and then divided by 100, making the real
    # default 0.05%. Five percent is what the help text always promised.
    parser.add_argument("--annual-return", type=float, default=5.0)
    known = parser.parse_args(args)
    return _run(
        [
            "retire",
            "--current-age", str(known.current_age),
            "--retirement-age", str(known.retirement_age),
            "--current-savings", repr(known.current_savings),
            "--target", repr(known.retirement_savings),
            "--annual-return", repr(known.annual_return),
            "--inflation", "0",
        ],
        "retirement_calculator.py",
    )


def savings_goal_tracker(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Months to reach a savings goal.")
    parser.add_argument("--goal", type=float, required=True)
    parser.add_argument("--current-savings", type=float, required=True)
    parser.add_argument("--monthly-contribution", type=float, required=True)
    parser.add_argument("--apy", type=float, default=0.0,
                        help="interest earned (the original ignored interest entirely)")
    known = parser.parse_args(args)
    argv = [
        "savings",
        "--goal", repr(known.goal),
        "--current-savings", repr(known.current_savings),
        "--contribution", repr(known.monthly_contribution),
    ]
    if known.apy:
        argv += ["--apy", repr(known.apy)]
    return _run(argv, "savings_goal_tracker.py")


ENTRY_POINTS: Dict[str, Callable[[Optional[List[str]]], int]] = {
    "biweekly_pay": biweekly_pay,
    "budget_planner": budget_planner,
    "debt_calculator": debt_calculator,
    "expense_tracker": expense_tracker,
    "investment_calculator": investment_calculator,
    "mortgage_calculator": mortgage_calculator,
    "retirement_calculator": retirement_calculator,
    "savings_goal_tracker": savings_goal_tracker,
}
