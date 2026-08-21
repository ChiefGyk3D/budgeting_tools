"""Command-line entry point.

``finplan <command> [options]``.  Every command shares the same output flags
(``--json``, ``--csv``, ``--detail``, ``--quiet``) and the same validation
types, so the tools compose rather than each behaving slightly differently.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .commands import (
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
from .core.tvm import NeverAmortizes

#: Registration order controls the order in ``finplan --help``.
COMMAND_MODULES = [
    budget,
    expenses,
    paychecks,
    savings,
    emergency_fund,
    debt,
    debt_plan,
    mortgage,
    refinance,
    investment,
    retirement,
    networth,
]

EPILOG = """\
examples:
  finplan mortgage --balance 285000 --original-principal 300000 --rate 6.25 \\
      --term 30 --start-date 2021-04-15 --extra-payment 250
  finplan debt-plan --file debts.csv --strategy avalanche --extra 300
  finplan retire --current-age 38 --retirement-age 65 --current-savings 220000 \\
      --monthly-contribution 1800 --annual-return 7 --inflation 3
  finplan budget --file budget.csv --income 7200 --detail
  finplan paychecks --first-payday 2026-01-02 --year 2026

Every command accepts --json for scripting and --csv to export its table.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="finplan",
        description="A personal financial planning toolkit.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"finplan {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    for module in COMMAND_MODULES:
        module.add_parser(subparsers)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return args.func(args) or 0
    except NeverAmortizes as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (ValueError, ArithmeticError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc.filename}: no such file", file=sys.stderr)
        return 2
    except BrokenPipeError:  # pragma: no cover - piping into head/less
        return 0
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
