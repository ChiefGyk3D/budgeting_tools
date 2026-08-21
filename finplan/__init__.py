"""finplan - a personal financial planning toolkit.

The package is organised in three layers:

``finplan.core``
    Pure, dependency-light financial primitives (money, rate conversions,
    time-value-of-money, amortisation, payment calendars).  Everything here
    is side-effect free and unit tested.
``finplan.commands``
    One module per CLI subcommand.  Each exposes ``add_parser(subparsers)``
    and a ``run(args)`` function.
``finplan.cli``
    Argument dispatch and shared output plumbing.

The core layer is importable on its own if you would rather drive the maths
from a notebook or another program::

    from finplan.core import amortize, LoanTerms, Frequency
"""

__version__ = "2.0.0"

__all__ = ["__version__"]
