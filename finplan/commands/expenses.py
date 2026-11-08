"""``finplan expenses`` -- record spending and report on it.

``expense_tracker.py`` could only append to a hardcoded ``expenses.csv``: no
header row, no category, no way to read anything back.  This keeps the same
one-line-to-record ergonomics and adds the half that was missing.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import os
from collections import OrderedDict
from decimal import Decimal
from typing import Dict, List

from .. import argtypes
from ..core.money import ZERO, dec, fmt_money, money
from ..loaders import DataFileError
from ..output import Report, emit
from ._common import add_output_args

NAME = "expenses"
ALIASES = ("expense",)
HELP = "Record expenses to a CSV ledger and report on what you have spent"

FIELDS = ["date", "amount", "category", "description", "recurring"]

#: Where the ledger lives when no ``--file`` is given.  The environment
#: variable makes it easy to keep separate ledgers per household or per year.
DEFAULT_LEDGER = os.environ.get(
    "FINPLAN_LEDGER", os.path.join(os.path.expanduser("~"), ".finplan", "expenses.csv")
)


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        aliases=list(ALIASES),
        help=HELP,
        description=(
            "A small CSV-backed expense ledger. 'add' appends a row, 'list' prints "
            "the rows matching a filter, and 'report' summarises by category and month."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--file", default=DEFAULT_LEDGER, metavar="PATH",
                        help="ledger file (also settable via the FINPLAN_LEDGER environment variable)")
    actions = parser.add_subparsers(dest="action", metavar="ACTION")

    add = actions.add_parser("add", help="record an expense")
    add.add_argument("--amount", type=argtypes.positive_amount, required=True)
    add.add_argument("--description", required=True)
    add.add_argument("--category", default="uncategorised")
    add.add_argument("--date", type=argtypes.date, metavar="YYYY-MM-DD",
                     help="date of the expense (default: today)")
    add.add_argument("--recurring", action="store_true", help="mark as a recurring expense")
    add.set_defaults(action="add")

    listing = actions.add_parser("list", help="print matching ledger rows")
    _add_filters(listing)
    add_output_args(listing)
    listing.set_defaults(action="list")

    report = actions.add_parser("report", help="summarise spending by category and month")
    _add_filters(report)
    report.add_argument("--top", type=argtypes.positive_int, default=10,
                        help="how many individual expenses to list in the largest-expenses table")
    add_output_args(report)
    report.set_defaults(action="report")

    parser.set_defaults(func=run, action=None)
    return parser


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--since", type=argtypes.date, metavar="YYYY-MM-DD")
    parser.add_argument("--until", type=argtypes.date, metavar="YYYY-MM-DD")
    parser.add_argument("--category", action="append",
                        help="only this category; repeatable")
    parser.add_argument("--recurring-only", action="store_true")
    parser.add_argument("--one-off-only", action="store_true")


def append_expense(path: str, row: Dict[str, object]) -> None:
    """Append one row, writing the header if the ledger is new."""
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def read_ledger(path: str) -> List[Dict[str, object]]:
    if not os.path.exists(path):
        raise FileNotFoundError(2, "no such file", path)
    rows: List[Dict[str, object]] = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "amount" not in [
            (f or "").strip().lower() for f in reader.fieldnames
        ]:
            raise DataFileError(
                f"{path}: not a finplan ledger (expected a header row with "
                f"columns: {', '.join(FIELDS)})"
            )
        for number, raw in enumerate(reader, start=2):
            record = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            if not record.get("amount"):
                continue
            try:
                amount = dec(record["amount"].replace(",", "").replace("$", ""))
            except ArithmeticError:
                raise DataFileError(f"{path}:{number}: amount {record['amount']!r} is not a number")
            try:
                date = _dt.datetime.strptime(record.get("date", ""), "%Y-%m-%d").date()
            except ValueError:
                raise DataFileError(
                    f"{path}:{number}: date {record.get('date')!r} is not YYYY-MM-DD"
                )
            rows.append(
                {
                    "date": date,
                    "amount": money(amount),
                    "category": record.get("category") or "uncategorised",
                    "description": record.get("description", ""),
                    "recurring": str(record.get("recurring", "")).lower()
                    in ("true", "yes", "1", "y"),
                }
            )
    return sorted(rows, key=lambda r: r["date"])


def apply_filters(rows: List[Dict[str, object]], args) -> List[Dict[str, object]]:
    if args.recurring_only and args.one_off_only:
        raise SystemExit("--recurring-only and --one-off-only are mutually exclusive")
    categories = {c.lower() for c in (args.category or [])}
    out = []
    for row in rows:
        if args.since and row["date"] < args.since:
            continue
        if args.until and row["date"] > args.until:
            continue
        if categories and str(row["category"]).lower() not in categories:
            continue
        if args.recurring_only and not row["recurring"]:
            continue
        if args.one_off_only and row["recurring"]:
            continue
        out.append(row)
    return out


def run(args) -> int:
    if args.action is None:
        raise SystemExit(
            "finplan expenses needs an action: add, list or report "
            "(try 'finplan expenses --help')"
        )
    if args.action == "add":
        date = args.date or _dt.date.today()
        append_expense(
            args.file,
            {
                "date": date.isoformat(),
                "amount": format(money(args.amount), "f"),
                "category": args.category,
                "description": args.description,
                "recurring": "true" if args.recurring else "false",
            },
        )
        marker = " (recurring)" if args.recurring else ""
        print(
            f"Recorded {fmt_money(args.amount)} on {date.isoformat()} "
            f"[{args.category}] {args.description}{marker} -> {args.file}"
        )
        return 0

    rows = apply_filters(read_ledger(args.file), args)
    if not rows:
        print("No expenses match that filter.")
        return 0

    total = sum((r["amount"] for r in rows), ZERO)
    if args.action == "list":
        report = Report(f"Expenses: {len(rows)} rows", args.file)
        report.money("Total", total)
        report.table(
            "Expenses",
            ["Date", "Amount", "Category", "Description", "Recurring"],
            [[r["date"], r["amount"], r["category"], r["description"],
              "yes" if r["recurring"] else ""] for r in rows],
            preview_rows=50,
        )
        args.detail = True
        emit(report, args)
        return 0

    # -- report -----------------------------------------------------------
    first, last = rows[0]["date"], rows[-1]["date"]
    months: OrderedDict[str, Decimal] = OrderedDict()
    by_category: Dict[str, Decimal] = {}
    recurring_total = ZERO
    for row in rows:
        key = f"{row['date'].year}-{row['date'].month:02d}"
        months[key] = months.get(key, ZERO) + row["amount"]
        by_category[row["category"]] = by_category.get(row["category"], ZERO) + row["amount"]
        if row["recurring"]:
            recurring_total += row["amount"]
    month_count = max(len(months), 1)

    report = Report(
        f"Expense report: {first.isoformat()} to {last.isoformat()}",
        f"{len(rows)} expenses across {len(by_category)} categories in {args.file}",
    )
    report.money("Total spent", total)
    report.money("Average per month", money(total / month_count))
    report.money("Largest single expense", max(r["amount"] for r in rows))
    report.money("Recurring spending", recurring_total)
    report.money("One-off spending", total - recurring_total)
    report.percent("Recurring share", recurring_total / total if total else ZERO)

    busiest = max(months.items(), key=lambda kv: kv[1])
    report.section("Months")
    report.add("Months covered", len(months))
    report.add("Most expensive month", f"{busiest[0]} ({fmt_money(busiest[1])})")

    report.table(
        "By category",
        ["Category", "Total spend", "Share", "Average per month", "Count"],
        [
            [
                category,
                amount,
                f"{amount / total * 100:.1f}%",
                money(amount / month_count),
                sum(1 for r in rows if r["category"] == category),
            ]
            for category, amount in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
        ],
    )
    report.table(
        "By month",
        ["Month", "Total spend", "Expenses"],
        [
            [key, amount, sum(1 for r in rows if f"{r['date'].year}-{r['date'].month:02d}" == key)]
            for key, amount in months.items()
        ],
    )
    report.table(
        f"Largest {args.top} expenses",
        ["Date", "Amount", "Category", "Description"],
        [
            [r["date"], r["amount"], r["category"], r["description"]]
            for r in sorted(rows, key=lambda r: r["amount"], reverse=True)[: args.top]
        ],
    )
    emit(report, args)
    return 0
