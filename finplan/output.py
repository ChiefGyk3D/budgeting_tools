"""Report building and rendering.

Commands build a :class:`Report` rather than calling ``print``.  That single
change is what lets every command support ``--json`` (for piping into other
tools) and ``--csv`` (for a spreadsheet) without each one growing its own
serialisation code, and it keeps the numbers separate from their formatting.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .core.money import fmt_money, fmt_pct

def is_money_column(rows: Sequence[Sequence[Any]], index: int) -> bool:
    """A column is currency when every value in it is a Decimal.

    Detecting by value rather than by column name means a new table gets its
    formatting right without anyone remembering to add a keyword: integers
    (counts, ages, payment numbers) stay plain, and Decimals render as money.
    """
    seen = False
    for row in rows:
        if index >= len(row):
            continue
        value = row[index]
        if value is None or value == "":
            continue
        if not isinstance(value, Decimal):
            return False
        seen = True
    return seen


@dataclass
class Table:
    name: str
    columns: Sequence[str]
    rows: List[Sequence[Any]] = field(default_factory=list)
    #: Rows to show when rendering as text.  A 360-row amortisation schedule
    #: is unreadable in a terminal; ``--csv`` always writes every row.
    preview_rows: Optional[int] = None

    def as_records(self) -> List[Dict[str, Any]]:
        return [dict(zip(self.columns, row)) for row in self.rows]


@dataclass
class Line:
    label: str
    value: Any
    note: Optional[str] = None
    kind: str = "text"  # text | money | percent


@dataclass
class Section:
    title: Optional[str]
    lines: List[Line] = field(default_factory=list)


class Report:
    """An ordered collection of sections, tables and notes."""

    def __init__(self, title: str, subtitle: Optional[str] = None) -> None:
        self.title = title
        self.subtitle = subtitle
        self.sections: List[Section] = [Section(title=None)]
        self.tables: List[Table] = []
        self.notes: List[str] = []
        self.warnings: List[str] = []

    # -- building -------------------------------------------------------
    def section(self, title: str) -> "Report":
        self.sections.append(Section(title=title))
        return self

    def add(self, label: str, value: Any, note: Optional[str] = None) -> "Report":
        self.sections[-1].lines.append(Line(label, value, note, "text"))
        return self

    def money(self, label: str, value: Any, note: Optional[str] = None) -> "Report":
        self.sections[-1].lines.append(Line(label, value, note, "money"))
        return self

    def percent(self, label: str, value: Any, note: Optional[str] = None) -> "Report":
        self.sections[-1].lines.append(Line(label, value, note, "percent"))
        return self

    def table(
        self,
        name: str,
        columns: Sequence[str],
        rows: Iterable[Sequence[Any]],
        *,
        preview_rows: Optional[int] = None,
    ) -> Table:
        table = Table(
            name=name,
            columns=list(columns),
            rows=[list(r) for r in rows],
            preview_rows=preview_rows,
        )
        self.tables.append(table)
        return table

    def note(self, text: str) -> "Report":
        self.notes.append(text)
        return self

    def warn(self, text: str) -> "Report":
        self.warnings.append(text)
        return self

    # -- rendering ------------------------------------------------------
    @staticmethod
    def _format(line: Line) -> str:
        if line.value is None:
            return "n/a"
        if line.kind == "money":
            return fmt_money(line.value)
        if line.kind == "percent":
            return fmt_pct(line.value)
        return str(line.value)

    def render_text(self, *, width: int = 78, show_tables: bool = True) -> str:
        out: List[str] = []
        out.append(self.title)
        out.append("=" * min(len(self.title), width))
        if self.subtitle:
            out.append(self.subtitle)
        for section in self.sections:
            if not section.lines:
                continue
            if section.title:
                out.append("")
                out.append(section.title)
                out.append("-" * min(len(section.title), width))
            label_width = max(len(l.label) for l in section.lines)
            for line in section.lines:
                text = f"  {line.label:<{label_width}}  {self._format(line)}"
                if line.note:
                    text += f"   ({line.note})"
                out.append(text)
        if show_tables:
            for table in self.tables:
                out.append("")
                out.append(render_table(table, max_rows=table.preview_rows))
        if self.warnings:
            out.append("")
            for warning in self.warnings:
                out.append(f"!  {warning}")
        if self.notes:
            out.append("")
            for note in self.notes:
                out.append(f"   {note}")
        return "\n".join(out)

    def to_dict(self, *, include_tables: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {"title": self.title}
        if self.subtitle:
            data["subtitle"] = self.subtitle
        results: Dict[str, Any] = {}
        for section in self.sections:
            bucket = results
            if section.title:
                bucket = results.setdefault(_slug(section.title), {})
            for line in section.lines:
                bucket[_slug(line.label)] = _jsonable(line.value)
        data["results"] = results
        if include_tables and self.tables:
            data["tables"] = {
                _slug(t.name): [
                    {_slug(k): _jsonable(v) for k, v in record.items()}
                    for record in t.as_records()
                ]
                for t in self.tables
            }
        if self.warnings:
            data["warnings"] = list(self.warnings)
        if self.notes:
            data["notes"] = list(self.notes)
        return data


def _slug(text: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "_" for c in text)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


def render_table(table: Table, *, max_rows: Optional[int] = None) -> str:
    """Render a table, right-aligning numeric columns and formatting money."""
    rows = table.rows if max_rows is None else table.rows[:max_rows]
    money_cols = {i for i in range(len(table.columns)) if is_money_column(rows, i)}

    def cell(index: int, value: Any) -> str:
        if value is None:
            return ""
        if index in money_cols:
            return fmt_money(value)
        return str(value)

    body = [[cell(i, v) for i, v in enumerate(row)] for row in rows]
    widths = [len(c) for c in table.columns]
    for row in body:
        for i, text in enumerate(row):
            widths[i] = max(widths[i], len(text))
    numeric = {
        i
        for i in range(len(table.columns))
        if rows and all(_is_numberish(r[i]) for r in rows if i < len(r))
    }

    def justify(index: int, text: str) -> str:
        return text.rjust(widths[index]) if index in numeric else text.ljust(widths[index])

    out = [table.name] if table.name else []
    out.append("  ".join(justify(i, c) for i, c in enumerate(table.columns)).rstrip())
    out.append("  ".join("-" * w for w in widths))
    out.extend(
        "  ".join(justify(i, c) for i, c in enumerate(row)).rstrip() for row in body
    )
    if max_rows is not None and len(table.rows) > max_rows:
        out.append(f"... {len(table.rows) - max_rows} more rows (use --csv to write them all)")
    return "\n".join(out)


def _is_numberish(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def write_csv(table: Table, path: str) -> None:
    """Write ``table`` to ``path``; ``-`` writes to stdout."""
    handle = sys.stdout if path == "-" else open(path, "w", newline="", encoding="utf-8")
    try:
        writer = csv.writer(handle)
        writer.writerow(table.columns)
        for row in table.rows:
            writer.writerow(
                [
                    # Plain numbers, not "$1,234.56": spreadsheets should get
                    # values they can sum, not pre-formatted strings.
                    format(v, "f") if isinstance(v, Decimal) else
                    (v.isoformat() if hasattr(v, "isoformat") else v)
                    for v in row
                ]
            )
    finally:
        if handle is not sys.stdout:
            handle.close()


def emit(report: Report, args) -> None:
    """Render ``report`` according to the shared ``--json`` / ``--csv`` flags."""
    csv_path = getattr(args, "csv", None)
    if csv_path:
        if not report.tables:
            raise SystemExit("this command produces no table to write as CSV")
        write_csv(report.tables[0], csv_path)
        if csv_path != "-" and not getattr(args, "json", False) and not getattr(args, "quiet", False):
            print(f"Wrote {len(report.tables[0].rows)} rows to {csv_path}", file=sys.stderr)

    if getattr(args, "json", False):
        print(json.dumps(report.to_dict(include_tables=getattr(args, "detail", False)), indent=2))
        return

    if getattr(args, "quiet", False):
        return

    print(report.render_text(show_tables=getattr(args, "detail", False)))
