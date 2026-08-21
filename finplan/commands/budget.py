"""``finplan budget`` -- category budget, surplus, savings rate and 50/30/20.

Replaces ``budget_planner.py``, which required eighteen hardcoded ``--dog-insurance``
style flags and had no relationship to the ``--category/--amount`` interface the
README documented.  Categories now come from a file or from repeatable flags.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Dict, List, Tuple

from .. import argtypes
from ..core.money import ZERO, dec, fmt_money, money
from ..loaders import DataFileError, load_records, parse_amount, pick, require_columns
from ..output import Report, emit
from ._common import add_output_args

NAME = "budget"
HELP = "Total a category budget and check it against your income"

GROUPS = ("needs", "wants", "savings")

#: The 50/30/20 rule: half of take-home to needs, 30% to wants, 20% to saving
#: and debt payoff.  Used only as a reference line, never as a hard rule.
RULE_503020 = {"needs": dec("0.50"), "wants": dec("0.30"), "savings": dec("0.20")}

#: Keyword -> group, for categories that do not declare a group themselves.
#: Matched as a substring against the lower-cased category name.
GROUP_KEYWORDS: List[Tuple[str, str]] = [
    ("rent", "needs"), ("mortgage", "needs"), ("property tax", "needs"),
    ("hoa", "needs"), ("insurance", "needs"), ("utilit", "needs"),
    ("electric", "needs"), ("gas bill", "needs"), ("water", "needs"),
    ("sewer", "needs"), ("trash", "needs"), ("internet", "needs"),
    ("phone", "needs"), ("grocer", "needs"), ("medical", "needs"),
    ("health", "needs"), ("pharmac", "needs"), ("childcare", "needs"),
    ("daycare", "needs"), ("tuition", "needs"), ("transit", "needs"),
    ("fuel", "needs"), ("commut", "needs"), ("car payment", "needs"),
    ("minimum payment", "needs"), ("alarm", "needs"), ("security", "needs"),
    ("student loan", "savings"), ("debt", "savings"), ("loan payment", "savings"),
    ("saving", "savings"), ("invest", "savings"), ("401", "savings"),
    ("ira", "savings"), ("brokerage", "savings"), ("emergency", "savings"),
    ("retirement", "savings"), ("hsa", "savings"), ("529", "savings"),
    ("rainy", "savings"), ("extra principal", "savings"),
    ("dining", "wants"), ("restaurant", "wants"), ("entertain", "wants"),
    ("subscription", "wants"), ("streaming", "wants"), ("travel", "wants"),
    ("vacation", "wants"), ("hobby", "wants"), ("shopping", "wants"),
    ("clothing", "wants"), ("gift", "wants"), ("coffee", "wants"),
    ("gym", "wants"), ("pet", "wants"),
]

FILE_HELP = """\
CSV or JSON of budget categories. Recognised columns:
  category   name of the line item (required)
  amount     planned spend for the period (required)
  group      needs | wants | savings (optional; inferred from the name if absent)
  notes      free text (optional)

Example budget.csv:
  category,amount,group
  Mortgage,1850,needs
  Groceries,650,needs
  Dining out,220,wants
  401k,900,savings
"""


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        help=HELP,
        description=(
            "Adds up a category budget, compares it against income, and reports the "
            "surplus, the savings rate and how the split compares with 50/30/20."
        ),
        epilog=FILE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", metavar="PATH", help="CSV or JSON of budget categories")
    source.add_argument(
        "--category",
        action="append",
        metavar="NAME=AMOUNT[:GROUP]",
        help="a category given inline; repeatable, e.g. --category 'Groceries=650:needs'",
    )
    parser.add_argument("--income", type=argtypes.positive_amount, required=True,
                        help="take-home income for the same period as the categories")
    parser.add_argument("--period", default="month",
                        help="label for the budgeting period, used in the report text")
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def infer_group(category: str) -> str:
    """Best-effort group for a category name; defaults to ``wants``.

    Defaulting to ``wants`` is deliberate: an unrecognised line is more likely
    discretionary than essential, and over-stating needs would flatter the
    50/30/20 comparison.
    """
    lowered = category.lower()
    for keyword, group in GROUP_KEYWORDS:
        if keyword in lowered:
            return group
    return "wants"


def parse_inline(specs: List[str]) -> List[dict]:
    rows = []
    for spec in specs:
        if "=" not in spec:
            raise SystemExit(f"--category expects NAME=AMOUNT[:GROUP], got {spec!r}")
        name, rest = spec.split("=", 1)
        group = None
        if ":" in rest:
            rest, group = rest.rsplit(":", 1)
            group = group.strip().lower()
            if group not in GROUPS:
                raise SystemExit(
                    f"--category {spec!r}: group must be one of {', '.join(GROUPS)}"
                )
        rows.append(
            {
                "category": name.strip(),
                "amount": parse_amount(rest, where=f"--category {name}", field="amount"),
                "group": group,
            }
        )
    return rows


def load_categories(path: str) -> List[dict]:
    records = load_records(path)
    require_columns(records, [("category", "name", "item"), ("amount", "budget", "planned")], path)
    rows = []
    for record in records:
        where = record.get("_where", path)
        name = str(pick(record, "category", "name", "item") or "").strip()
        if not name:
            raise DataFileError(f"{where}: category name is required")
        group = pick(record, "group", "type", "bucket")
        group = str(group).strip().lower() if group else None
        if group and group not in GROUPS:
            group = None
        rows.append(
            {
                "category": name,
                "amount": parse_amount(
                    pick(record, "amount", "budget", "planned"), where=where, field="amount"
                ),
                "group": group,
                "notes": pick(record, "notes", "note", "comment"),
            }
        )
    return rows


def run(args) -> int:
    rows = load_categories(args.file) if args.file else parse_inline(args.category)
    for row in rows:
        row["inferred"] = not row.get("group")
        row["group"] = row.get("group") or infer_group(row["category"])

    planned = sum((r["amount"] for r in rows), ZERO)
    surplus = args.income - planned
    by_group: Dict[str, Decimal] = {g: ZERO for g in GROUPS}
    for row in rows:
        by_group[row["group"]] += row["amount"]

    period = args.period
    report = Report(
        f"Budget: {len(rows)} categories against {fmt_money(args.income)} per {period}",
    )
    report.money(f"Income per {period}", args.income)
    report.money("Planned spending and saving", planned)
    report.money("Unallocated" if surplus >= 0 else "Over budget by", abs(surplus))
    report.percent("Share of income allocated", planned / args.income)

    savings = by_group["savings"] + max(surplus, ZERO)
    report.money("Going to savings and debt payoff", by_group["savings"])
    report.percent("Savings rate", by_group["savings"] / args.income)
    if surplus > 0:
        report.percent("Savings rate if the surplus is saved too", savings / args.income)

    if surplus < 0:
        report.warn(
            f"The budget spends {fmt_money(-surplus)} more than it takes in each {period}. "
            "Either income is understated or a category has to come down."
        )
    elif surplus == 0:
        report.note("Every dollar is allocated - a zero-based budget.")

    report.section("50/30/20 comparison")
    for group in GROUPS:
        actual = by_group[group]
        reference = money(args.income * RULE_503020[group])
        share = actual / args.income if args.income else ZERO
        delta = actual - reference
        direction = "over" if delta > 0 else "under"
        report.add(
            group.capitalize(),
            f"{fmt_money(actual)} ({share * 100:.1f}%) - "
            f"{fmt_money(abs(delta))} {direction} the {RULE_503020[group] * 100:.0f}% reference",
        )
    report.note(
        "50/30/20 is a starting point, not a rule. A high-cost housing market or an "
        "aggressive debt payoff plan both move these numbers legitimately."
    )

    ordered = sorted(rows, key=lambda r: r["amount"], reverse=True)
    report.table(
        "Categories",
        ["Category", "Group", "Amount", "Share of income", "Share of budget"],
        [
            [
                row["category"],
                row["group"],
                row["amount"],
                f"{row['amount'] / args.income * 100:.1f}%",
                f"{row['amount'] / planned * 100:.1f}%" if planned else "-",
            ]
            for row in ordered
        ],
    )
    report.table(
        "By group",
        ["Group", "Amount", "Share of income", "50/30/20 reference", "Difference"],
        [
            [
                group,
                by_group[group],
                f"{by_group[group] / args.income * 100:.1f}%",
                money(args.income * RULE_503020[group]),
                money(by_group[group] - args.income * RULE_503020[group]),
            ]
            for group in GROUPS
        ],
    )
    if any(r["inferred"] for r in rows):
        inferred = [r["category"] for r in rows if r["inferred"]]
        report.note(
            f"Group inferred from the name for {len(inferred)} categories "
            f"({', '.join(inferred[:5])}{', ...' if len(inferred) > 5 else ''}); "
            "set a 'group' column or ':needs'/':wants'/':savings' to override."
        )
    emit(report, args)
    return 0
