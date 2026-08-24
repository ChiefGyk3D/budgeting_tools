"""Reading user data files.

Every file-driven command (debts, budget categories, net-worth accounts)
accepts the same two formats -- CSV with a header row, or JSON -- and reports
problems with the file name and line number rather than raising a bare
``KeyError`` from somewhere deep in the command.
"""

from __future__ import annotations

import csv
import json
import os
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .core.money import dec


class DataFileError(ValueError):
    """A user data file could not be understood."""


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_amount(value: Any, *, where: str, field: str, default: Optional[Decimal] = None) -> Decimal:
    text = _clean(value).replace(",", "").replace("$", "")
    if not text:
        if default is not None:
            return default
        raise DataFileError(f"{where}: missing required column {field!r}")
    try:
        return dec(text)
    except (InvalidOperation, ArithmeticError):
        raise DataFileError(f"{where}: {field}={value!r} is not a number")


def parse_rate(value: Any, *, where: str, field: str, default: Optional[Decimal] = None) -> Decimal:
    """Read a rate column, accepting ``6.5``, ``6.5%`` or ``0.065``.

    A bare value at or below 1 is read as a fraction, which is what people
    typically mean when they type ``0.065`` into a spreadsheet.
    """
    text = _clean(value).replace("%", "")
    if not text:
        if default is not None:
            return default
        raise DataFileError(f"{where}: missing required column {field!r}")
    try:
        number = dec(text)
    except (InvalidOperation, ArithmeticError):
        raise DataFileError(f"{where}: {field}={value!r} is not a number")
    if number < 0:
        raise DataFileError(f"{where}: {field}={value!r} must not be negative")
    explicit_percent = "%" in _clean(value)
    return number if (number <= 1 and not explicit_percent) else number / 100


def load_records(path: str) -> List[Dict[str, Any]]:
    """Load a list of records from a ``.json`` or ``.csv`` file.

    Column names are lower-cased and internal spaces become underscores, so
    ``"Minimum Payment"`` and ``minimum_payment`` are the same column.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(2, "no such file", path)
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as handle:
            try:
                data = json.load(handle)
            except json.JSONDecodeError as exc:
                raise DataFileError(f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}")
        if isinstance(data, dict):
            # Accept {"debts": [...]} / {"categories": [...]} wrappers.
            for value in data.values():
                if isinstance(value, list):
                    data = value
                    break
            else:
                data = [data]
        if not isinstance(data, list):
            raise DataFileError(f"{path}: expected a JSON list of objects")
        return [_normalise_keys(row, path) for row in data]

    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(_strip_comments(handle))
        if reader.fieldnames is None:
            raise DataFileError(f"{path}: the file is empty; a header row is required")
        rows = []
        for number, row in enumerate(reader, start=2):
            if not any(_clean(v) for v in row.values()):
                continue
            record = _normalise_keys(row, f"{path}:{number}")
            record["_where"] = f"{path}:{number}"
            rows.append(record)
        if not rows:
            raise DataFileError(f"{path}: no data rows found below the header")
        return rows


def _strip_comments(lines: Iterable[str]) -> Iterable[str]:
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        yield line


def _normalise_keys(row: Any, where: str) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise DataFileError(f"{where}: expected an object/row, got {type(row).__name__}")
    out: Dict[str, Any] = {}
    for key, value in row.items():
        if key is None:
            continue
        out[str(key).strip().lower().replace(" ", "_").replace("-", "_")] = value
    return out


def pick(record: Dict[str, Any], *names: str) -> Any:
    """First present, non-empty value among ``names``."""
    for name in names:
        if name in record and _clean(record[name]):
            return record[name]
    return None


def require_columns(records: Sequence[Dict[str, Any]], required: Sequence[Sequence[str]], path: str) -> None:
    """Fail early, naming every missing column and what the file does have."""
    present = set()
    for record in records:
        present.update(record.keys())
    missing = [group[0] for group in required if not any(name in present for name in group)]
    if missing:
        have = ", ".join(sorted(k for k in present if not k.startswith("_"))) or "(none)"
        raise DataFileError(
            f"{path}: missing required column(s): {', '.join(missing)}. Found: {have}"
        )
