# Budgeting Tools

A personal financial planning toolkit. One command, `finplan`, covering budgets,
expense tracking, pay calendars, savings goals, debt payoff, mortgages,
refinancing, investments, retirement and net worth — all sharing the same
financial engine, the same input validation and the same output formats.

```
finplan mortgage --balance 285000 --original-principal 300000 --rate 6.25 \
    --term 30 --start-date 2026-09-01 --extra-payment 250
```

```
Loan summary: $285,000.00 at 6.250% over 30 years
=================================================
Monthly payments starting 2026-09-01
  Scheduled payment (per month)  $1,847.15
  Extra principal (per month)    $250.00
  Total outlay (per month)       $2,097.15

Payoff
------
  Payments remaining  237
  Time to payoff      19 years, 9 months
  Payoff date         2046-05-01
  Total interest      $211,688.11

Effect of extra payments
------------------------
  Interest saved      $82,053.57
  Payments saved      77
  Time saved          6 years, 5 months
```

## Install

```
git clone https://github.com/ChiefGyk3D/budgeting_tools.git
cd budgeting_tools
pip install -e .
```

Python 3.8 or newer. **No third-party dependencies** — the calendar maths that
previously needed `python-dateutil` is now in `finplan/core/dates.py`.

Without installing, `python -m finplan <command>` works from the repository root.

## Commands

| Command | What it does |
|---|---|
| `finplan budget` | Total a category budget, report surplus, savings rate and a 50/30/20 comparison |
| `finplan expenses` | Record expenses to a CSV ledger (`add`) and summarise them (`list`, `report`) |
| `finplan paychecks` | Build a pay calendar and find the months with an extra paycheck |
| `finplan savings` | Time to reach a savings goal, or the contribution a deadline requires |
| `finplan emergency-fund` | Size an emergency fund and time how long it takes to build |
| `finplan debt` | Payoff time and total interest for one balance, plus a pay-more table |
| `finplan debt-plan` | Order several debts by avalanche or snowball and compare the cost |
| `finplan mortgage` | Full amortisation schedule, payoff date, extra-payment savings, PMI and escrow |
| `finplan refinance` | Compare a loan against a refinance, with break-even and lifetime interest |
| `finplan invest` | Project a portfolio with fees, contribution growth and inflation |
| `finplan retire` | Project retirement savings, or solve for the contribution you need |
| `finplan networth` | Total assets and liabilities, with liquidity and period-on-period change |

`finplan <command> --help` documents every flag. Aliases exist for the obvious
alternatives (`loan` for `mortgage`, `investment` for `invest`, and so on).

## Shared options

Every command accepts the same output flags, so the tools compose:

| Flag | Effect |
|---|---|
| `--json` | Machine-readable output for scripting |
| `--csv PATH` | Write the command's main table to a CSV (`-` for stdout) |
| `--detail` | Include the full table in the report, not just the summary |
| `--quiet` | Suppress the human-readable report |
| `--as-of DATE` | Evaluate as of a fixed date, so output is reproducible |

```bash
# Export a full 360-row amortisation schedule for a spreadsheet
finplan mortgage --balance 300000 --rate 6 --term 30 \
    --start-date 2026-01-31 --csv schedule.csv --quiet

# Pull one number out for a script
finplan debt --balance 5400 --rate 22.9 --payment 200 --json \
    | jq '.results.total_interest'
```

## Worked examples

Sample data files live in [`examples/`](examples/).

### Pay off several debts

```bash
finplan debt-plan --file examples/debts.csv --extra 400
```

Pays every minimum, throws the spare cash at one target at a time, and rolls each
cleared debt's minimum into the next. Both strategies are simulated against the
same budget, so the real cost of choosing snowball for motivation is visible:

```
  Avalanche  43 payments, $5,613.19 interest  <- cheapest
  Snowball   43 payments, $5,821.47 interest

   Snowball costs $208.28 more but clears 'Store card' in 3 payments,
   which some people need to stay with the plan.
```

### Should you refinance?

```bash
finplan refinance --balance 268000 --rate 6.75 --remaining-term 24 \
    --new-rate 5.5 --new-term 30 --closing-costs 6500
```

Reports break-even, and catches the trap a lower rate hides — a longer term can
cost *more* in total interest — along with what happens if you refinance and keep
paying the old amount.

### Budget against income

```bash
finplan budget --file examples/budget.csv --income 7200
```

Categories can also be given inline:

```bash
finplan budget --income 5000 --category 'Rent=1500:needs' \
    --category 'Fun=300:wants' --category 'IRA=500:savings'
```

The group (`needs`/`wants`/`savings`) is inferred from the category name when
you leave it out, and the report says which ones were inferred.

### Track expenses

```bash
finplan expenses add --amount 82.14 --description 'Weekly shop' --category groceries
finplan expenses report --since 2026-01-01
finplan expenses report --category groceries --json
```

The ledger defaults to `~/.finplan/expenses.csv`; set `FINPLAN_LEDGER` or pass
`--file` to keep several.

### Find the three-paycheck months

```bash
finplan paychecks --first-payday 2026-01-02 --year 2026 --net-pay 2450
```

Those months are the natural place to send a debt payment or an annual bill,
because the ordinary budget is already covered by the usual two cheques.

## Data file formats

`debt-plan`, `budget` and `networth` all read CSV (with a header row) or JSON.
Column names are case-insensitive, `#` comment lines are skipped, and problems
are reported with the file and line number. Each command's `--help` lists the
columns it recognises.

## Rate conventions

The two conventions for "an annual rate" differ by thousands of dollars over
thirty years, so each command states which one it is using and lets you switch:

- **Nominal** (`--nominal-rate`): the rate is divided by the number of periods.
  This is how lenders quote loans, and it is the default for anything loan-shaped.
- **Effective** (`--effective-rate`): the rate is the actual annual yield, so the
  periodic rate is its *n*-th root. This is how market returns are quoted, and it
  is the default for `invest`, `retire` and `savings`.

Inflation adjustment uses the exact Fisher relation, `(1+r)/(1+i) - 1`, not the
`r - i` shortcut, which overstates real returns.

## Money handling

Every amount is a `Decimal`, quantised to cents with ROUND_HALF_UP at the
boundaries and carried at 34 digits internally. Binary floats cannot represent
`0.01`, so a float-based 360-row schedule drifts visibly by the final rows.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
```

145 tests cover the financial primitives, the amortisation engine, the debt
simulator, and the CLI end to end — including a regression test for each bug
listed below.

The layout separates the maths from the interface:

```
finplan/core/       pure financial primitives, no I/O
  money.py            Decimal handling and formatting
  rates.py            frequencies and rate conversions
  tvm.py              time-value-of-money formulas
  dates.py            month-end-safe payment calendars
  amortization.py     the loan engine
  payoff.py           multi-debt avalanche/snowball simulation
finplan/commands/   one module per subcommand
finplan/cli.py      dispatch
```

`finplan.core` is importable on its own if you would rather drive the maths from
a notebook:

```python
from finplan.core import LoanTerms, amortize, as_rate
import datetime

schedule = amortize(LoanTerms(
    balance=300000, annual_rate=as_rate(6), term_years=30,
    start_date=datetime.date(2026, 1, 31),
))
print(schedule.total_interest, schedule.payoff_date)
```

## Upgrading from the original scripts

The old scripts still work. Each is now a thin wrapper that takes its original
flags, runs the fixed engine, and prints the equivalent `finplan` command:

| Old script | New command |
|---|---|
| `biweekly_pay.py` | `finplan paychecks` |
| `budget_planner.py` | `finplan budget` |
| `debt_calculator.py` | `finplan debt` |
| `expense_tracker.py` | `finplan expenses add` |
| `investment_calculator.py` | `finplan invest` |
| `mortgage_calculator.py` | `finplan mortgage` |
| `retirement_calculator.py` | `finplan retire` |
| `savings_goal_tracker.py` | `finplan savings` |

Two behaviour changes worth knowing about:

- **`retirement_calculator.py` gave the wrong answer.** `--annual-return`
  defaulted to `0.05` and was then divided by 100, making the real default
  0.05% rather than the 5% the help text promised. For a 25-year horizon that
  overstated the required monthly saving by 2.3× ($4,633.50 instead of
  $1,982.75). The wrapper now defaults to a true 5%, so **your numbers will
  change** if you relied on the default.
- **`mortgage_calculator.py --start-date`** is now the date of the *next*
  payment on `--remaining-principal`, not the origination date. Pass
  `--origination-date` as well to see progress so far and a consistency check
  against the contract.

### Bugs fixed

| Where | Bug |
|---|---|
| `retirement_calculator.py` | `--annual-return` default of `0.05` divided by 100 → a 0.05% default rate |
| `retirement_calculator.py` | `ZeroDivisionError` when `--retirement-age` equalled `--current-age` |
| `retirement_calculator.py` | Printed a negative monthly saving when already on track |
| `debt_calculator.py` | `ValueError: math domain error` when the payment was below the accruing interest |
| `debt_calculator.py` | Reported `3.0 years and 2.3061771425855753 months` |
| `savings_goal_tracker.py` | `ZeroDivisionError` on a zero contribution; ignored interest entirely |
| `mortgage_calculator.py` | `ValueError: day is out of range for month` for any loan starting on the 29th–31st |
| `mortgage_calculator.py` | The whole computation block was duplicated verbatim (lines 38–130) |
| `mortgage_calculator.py` | `--output` wrote a schedule truncated at today, because the loop broke at the first future payment |
| `mortgage_calculator.py` | `extra_payment` was mutated inside the loop, corrupting every later row |
| `mortgage_calculator.py` | The payoff date was recomputed from scratch inside the per-payment loop (O(n²)) |
| `mortgage_calculator.py` | Infinite loop when the payment did not cover the interest |
| `mortgage_calculator.py` | Biweekly was modelled as re-amortising over 26·term periods, which shows no acceleration at all |
| `mortgage_calculator.py` | `payments_made` used `years*26 + months*2`, drifting by two payments a year |
| `biweekly_pay.py` | Hardcoded 26 paydays; a biweekly year can have 27 |
| `biweekly_pay.py` | Tallied by month *name*, so two Januaries in one window merged |
| `biweekly_pay.py` | Leaked the output file handle if writing failed |
| `budget_planner.py` | 18 hardcoded `required=True` category flags, none of them editable |
| `README.md` | Documented script names and flags that did not exist |

## Limitations

These are planning tools, not financial advice. They do not model taxes, credit
decisions, variable rates, market volatility or sequence-of-returns risk. A
projection assuming a constant 7% return is a useful reference point and nothing
more — real markets do not deliver one. Consult a financial advisor for advice
about your own situation.

## Contributing

Issues and pull requests welcome. Please add a test alongside any change to
`finplan/core` — the whole point of the split is that the maths is testable
without going through the CLI.

## License

[Apache License 2.0](LICENSE). Copyright 2023-2026 ChiefGyk3D.

Apache 2.0 was chosen over a copyleft license so the tools can be used inside
commercial products without obliging the user to open-source their own work. It
also carries an explicit patent grant, which MIT does not.
