"""One module per CLI subcommand.

Each module exposes ``NAME``, ``HELP``, ``add_parser(subparsers)`` and
``run(args)``.  Adding a command means writing the module and appending it to
``finplan.cli.COMMAND_MODULES``.
"""

from . import (
    budget,
    debt,
    debt_plan,
    emergency_fund,
    expenses,
    investment,
    mortgage,
    networth,
    paychecks,
    refinance,
    retirement,
    savings,
)

__all__ = [
    "budget", "debt", "debt_plan", "emergency_fund", "expenses", "investment",
    "mortgage", "networth", "paychecks", "refinance", "retirement", "savings",
]
