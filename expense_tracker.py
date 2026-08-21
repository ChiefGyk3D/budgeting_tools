#!/usr/bin/env python3
"""Compatibility wrapper. The maintained entry point is `finplan`.

Runs the same calculation through `finplan.commands`, translating the original
flags. See finplan/legacy.py for the mapping and README.md for the new syntax.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finplan.legacy import expense_tracker

if __name__ == "__main__":
    raise SystemExit(expense_tracker())
