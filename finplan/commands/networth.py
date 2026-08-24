"""``finplan networth`` -- assets minus liabilities, with a trend if you keep history."""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Dict, List

from ..core.money import ZERO, fmt_money
from ..loaders import DataFileError, load_records, parse_amount, pick, require_columns
from ..output import Report, emit
from ._common import add_output_args

NAME = "networth"
ALIASES = ("net-worth",)
HELP = "Total assets and liabilities into a net worth statement"

LIABILITY_WORDS = ("liability", "liabilities", "debt", "loan", "mortgage", "card", "owed")

FILE_HELP = """\
CSV or JSON of accounts. Recognised columns:
  name      account label (required)
  value     balance; positive numbers (required)
  kind      asset | liability (optional; inferred from the name or a negative value)
  category  grouping such as cash, retirement, property (optional)
  liquid    true/false, whether the asset can be reached quickly (optional)

Example accounts.csv:
  name,value,kind,category,liquid
  Checking,4200,asset,cash,true
  401k,186000,asset,retirement,false
  House,415000,asset,property,false
  Mortgage,268000,liability,property,
  Visa,2400,liability,credit,
"""


def add_parser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        NAME,
        aliases=list(ALIASES),
        help=HELP,
        description=(
            "Reads a list of accounts and reports net worth, the split between assets "
            "and liabilities, liquidity, and the change against an earlier snapshot."
        ),
        epilog=FILE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", metavar="PATH", help="CSV or JSON of accounts")
    source.add_argument("--account", action="append", metavar="NAME=VALUE[:KIND]",
                        help="an account given inline; repeatable")
    parser.add_argument("--previous", metavar="PATH",
                        help="an earlier snapshot to compare against")
    add_output_args(parser)
    parser.set_defaults(func=run)
    return parser


def classify(name: str, kind: object, value: Decimal) -> str:
    """Decide whether an account is an asset or a liability.

    An explicit ``kind`` column wins; otherwise a negative value or a
    debt-flavoured name marks it as a liability.
    """
    if kind:
        text = str(kind).strip().lower()
        if text.startswith("l") or text in ("debt", "owed"):
            return "liability"
        if text.startswith("a"):
            return "asset"
    if value < 0:
        return "liability"
    lowered = name.lower()
    if any(word in lowered for word in LIABILITY_WORDS):
        return "liability"
    return "asset"


def parse_inline(specs: List[str]) -> List[dict]:
    rows = []
    for spec in specs:
        if "=" not in spec:
            raise SystemExit(f"--account expects NAME=VALUE[:KIND], got {spec!r}")
        name, rest = spec.split("=", 1)
        kind = None
        if ":" in rest:
            rest, kind = rest.rsplit(":", 1)
        value = parse_amount(rest, where=f"--account {name}", field="value")
        rows.append(
            {
                "name": name.strip(),
                "value": value,
                "kind": classify(name, kind, value),
                "category": "",
                "liquid": None,
            }
        )
    return rows


def load_accounts(path: str) -> List[dict]:
    records = load_records(path)
    require_columns(records, [("name", "account", "label"), ("value", "balance", "amount")], path)
    rows = []
    for record in records:
        where = record.get("_where", path)
        name = str(pick(record, "name", "account", "label") or "").strip()
        if not name:
            raise DataFileError(f"{where}: name is required")
        value = parse_amount(pick(record, "value", "balance", "amount"), where=where, field="value")
        liquid_raw = pick(record, "liquid", "is_liquid")
        rows.append(
            {
                "name": name,
                "value": abs(value),
                "kind": classify(name, pick(record, "kind", "type"), value),
                "category": str(pick(record, "category", "group", "bucket") or "uncategorised"),
                "liquid": str(liquid_raw).strip().lower() in ("true", "yes", "1", "y")
                if liquid_raw is not None
                else None,
            }
        )
    return rows


def totals(rows: List[dict]) -> Dict[str, Decimal]:
    assets = sum((r["value"] for r in rows if r["kind"] == "asset"), ZERO)
    liabilities = sum((r["value"] for r in rows if r["kind"] == "liability"), ZERO)
    return {"assets": assets, "liabilities": liabilities, "net": assets - liabilities}


def run(args) -> int:
    rows = load_accounts(args.file) if args.file else parse_inline(args.account)
    if not rows:
        raise SystemExit("no accounts found")
    current = totals(rows)

    report = Report(
        f"Net worth: {fmt_money(current['net'])}",
        f"{len(rows)} accounts",
    )
    report.money("Total assets", current["assets"])
    report.money("Total liabilities", current["liabilities"])
    report.money("Net worth", current["net"])
    if current["assets"]:
        report.percent("Debt to assets", current["liabilities"] / current["assets"])
    if current["net"] < 0:
        report.warn("Liabilities exceed assets; net worth is negative.")

    liquid = sum(
        (r["value"] for r in rows if r["kind"] == "asset" and r["liquid"]), ZERO
    )
    if any(r["liquid"] for r in rows):
        report.section("Liquidity")
        report.money("Liquid assets", liquid)
        report.money("Illiquid assets", current["assets"] - liquid)
        report.percent(
            "Liquid share of assets", liquid / current["assets"] if current["assets"] else ZERO
        )

    if args.previous:
        before = totals(load_accounts(args.previous))
        change = current["net"] - before["net"]
        report.section("Change since the previous snapshot")
        report.money("Previous net worth", before["net"])
        report.money("Change", change)
        if before["net"]:
            report.percent("Percent change", change / abs(before["net"]))
        report.money("Change in assets", current["assets"] - before["assets"])
        report.money("Change in liabilities", current["liabilities"] - before["liabilities"])

    by_category: Dict[str, Dict[str, Decimal]] = {}
    for row in rows:
        bucket = by_category.setdefault(row["category"], {"asset": ZERO, "liability": ZERO})
        bucket[row["kind"]] += row["value"]

    report.table(
        "Accounts",
        ["Name", "Kind", "Category", "Value", "Share of total"],
        [
            [
                row["name"],
                row["kind"],
                row["category"],
                row["value"] if row["kind"] == "asset" else -row["value"],
                f"{row['value'] / current['assets'] * 100:.1f}%"
                if row["kind"] == "asset" and current["assets"]
                else "",
            ]
            for row in sorted(rows, key=lambda r: (r["kind"], -r["value"]))
        ],
    )
    report.table(
        "By category",
        ["Category", "Assets", "Liabilities", "Net"],
        [
            [category, values["asset"], values["liability"], values["asset"] - values["liability"]]
            for category, values in sorted(
                by_category.items(), key=lambda kv: kv[1]["asset"] - kv[1]["liability"], reverse=True
            )
        ],
    )
    emit(report, args)
    return 0
