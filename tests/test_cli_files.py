"""Tests for the file-driven commands and the shared output plumbing."""

import json

import pytest

DEBTS_CSV = """\
name,balance,rate,minimum
Visa,5400,22.9,135
Store card,1180,26.99,40
Car loan,14200,4.9,318
"""

BUDGET_CSV = """\
# a comment line, ignored
category,amount,group
Mortgage,1850,needs
Groceries,720,needs
Dining out,260,wants
401k,900,savings
Electric,130,
"""

ACCOUNTS_CSV = """\
name,value,kind,category,liquid
Checking,4200,asset,cash,true
401k,186000,asset,retirement,false
House,415000,asset,property,false
Mortgage,268000,liability,property,
Visa,5400,liability,credit,
"""


@pytest.fixture
def debts_file(tmp_path):
    path = tmp_path / "debts.csv"
    path.write_text(DEBTS_CSV)
    return str(path)


@pytest.fixture
def budget_file(tmp_path):
    path = tmp_path / "budget.csv"
    path.write_text(BUDGET_CSV)
    return str(path)


@pytest.fixture
def accounts_file(tmp_path):
    path = tmp_path / "accounts.csv"
    path.write_text(ACCOUNTS_CSV)
    return str(path)


# --------------------------------------------------------------------------
# debt-plan
# --------------------------------------------------------------------------
def test_debt_plan_from_csv(run_json, debts_file):
    results = run_json("debt-plan", "--file", debts_file, "--extra", "300")
    assert results["total_budget"] == 793.0
    assert results["payments_to_debt_free"] > 0
    comparison = results["strategy_comparison"]
    assert "avalanche" in comparison and "snowball" in comparison


def test_debt_plan_from_json_file(run_json, tmp_path):
    path = tmp_path / "debts.json"
    path.write_text(json.dumps({"debts": [
        {"name": "Visa", "balance": 5400, "rate": 22.9, "minimum": 135},
        {"name": "Car", "balance": 14200, "rate": "4.9%", "minimum": 318},
    ]}))
    results = run_json("debt-plan", "--file", str(path), "--extra", "200")
    assert results["minimum_payments"] == 453.0


def test_debt_plan_inline_debts(run_json):
    results = run_json("debt-plan", "--debt", "Visa:5400:22.9:135",
                       "--debt", "Car:14200:4.9:318", "--extra", "200")
    assert results["minimum_payments"] == 453.0


def test_debt_plan_reports_a_missing_column(run_cli, tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("name,balance\nVisa,5400\n")
    code, out, err = run_cli("debt-plan", "--file", str(path))
    assert code != 0
    message = out + err
    assert "missing required column" in message
    assert "rate" in message and "Found:" in message


def test_debt_plan_reports_a_bad_number_with_its_line(run_cli, tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("name,balance,rate,minimum\nVisa,not-a-number,22.9,135\n")
    code, out, err = run_cli("debt-plan", "--file", str(path))
    assert code != 0
    assert ":2:" in (out + err)


def test_debt_plan_rate_column_accepts_percent_or_fraction(run_json, tmp_path):
    as_percent = tmp_path / "a.csv"
    as_percent.write_text("name,balance,rate,minimum\nA,1000,10,50\n")
    as_fraction = tmp_path / "b.csv"
    as_fraction.write_text("name,balance,rate,minimum\nA,1000,0.10,50\n")
    assert run_json("debt-plan", "--file", str(as_percent))["total_interest"] == (
        run_json("debt-plan", "--file", str(as_fraction))["total_interest"]
    )


# --------------------------------------------------------------------------
# budget
# --------------------------------------------------------------------------
def test_budget_totals_and_savings_rate(run_json, budget_file):
    results = run_json("budget", "--file", budget_file, "--income", "7200")
    assert results["planned_spending_and_saving"] == 3860.0
    assert results["unallocated"] == 3340.0
    assert results["savings_rate"] == pytest.approx(900 / 7200)


def test_budget_infers_a_group_when_the_column_is_blank(run_cli, budget_file):
    """'Electric' has no group in the file; it should land in needs, not wants."""
    code, out, _ = run_cli("budget", "--file", budget_file, "--income", "7200", "--detail",
                           "--json")
    payload = json.loads(out)
    groups = {row["category"]: row["group"] for row in payload["tables"]["categories"]}
    assert groups["Electric"] == "needs"
    assert groups["Dining out"] == "wants"
    # 1850 + 720 + 130 inferred = 2700 of needs
    assert payload["results"]["50_30_20_comparison"]["needs"].startswith("$2,700.00")
    assert "inferred from the name" in " ".join(payload["notes"])


def test_budget_warns_when_over_income(run_cli, budget_file):
    code, out, _ = run_cli("budget", "--file", budget_file, "--income", "3000")
    assert code == 0
    assert "more than it takes in" in out


def test_budget_inline_categories_with_explicit_groups(run_json):
    results = run_json("budget", "--income", "5000",
                       "--category", "Rent=1500:needs",
                       "--category", "Fun=300:wants",
                       "--category", "IRA=500:savings")
    assert results["planned_spending_and_saving"] == 2300.0
    assert results["savings_rate"] == 0.1


def test_budget_rejects_a_bad_inline_group(run_cli):
    code, out, err = run_cli("budget", "--income", "5000", "--category", "Rent=1500:essential")
    assert code != 0
    assert "group must be one of" in (out + err)


# --------------------------------------------------------------------------
# networth
# --------------------------------------------------------------------------
def test_networth_totals(run_json, accounts_file):
    results = run_json("networth", "--file", accounts_file)
    assert results["total_assets"] == 605200.0
    assert results["total_liabilities"] == 273400.0
    assert results["net_worth"] == 331800.0


def test_networth_liquidity_split(run_json, accounts_file):
    results = run_json("networth", "--file", accounts_file)
    assert results["liquidity"]["liquid_assets"] == 4200.0


def test_networth_compares_two_snapshots(run_json, accounts_file, tmp_path):
    older = tmp_path / "old.csv"
    older.write_text(ACCOUNTS_CSV.replace("Checking,4200", "Checking,2200"))
    results = run_json("networth", "--file", accounts_file, "--previous", str(older))
    assert results["change_since_the_previous_snapshot"]["change"] == 2000.0


def test_networth_infers_liabilities_from_the_name(run_json):
    results = run_json("networth", "--account", "Savings=10000",
                       "--account", "Car loan=4000")
    assert results["total_assets"] == 10000.0
    assert results["total_liabilities"] == 4000.0


def test_networth_warns_when_negative(run_cli):
    code, out, _ = run_cli("networth", "--account", "Cash=1000", "--account", "Debt=5000")
    assert code == 0
    assert "negative" in out


# --------------------------------------------------------------------------
# expenses
# --------------------------------------------------------------------------
def test_expenses_round_trip(run_cli, tmp_path):
    ledger = str(tmp_path / "ledger.csv")
    for amount, category, date in (
        ("82.14", "groceries", "2026-06-03"),
        ("1850", "housing", "2026-06-01"),
        ("64.20", "dining", "2026-07-12"),
    ):
        code, _, _ = run_cli("expenses", "--file", ledger, "add", "--amount", amount,
                             "--description", "test", "--category", category, "--date", date)
        assert code == 0

    header = open(ledger).readline().strip()
    assert header == "date,amount,category,description,recurring"

    code, out, _ = run_cli("expenses", "--file", ledger, "report", "--json")
    assert code == 0
    results = json.loads(out)["results"]
    assert results["total_spent"] == pytest.approx(1996.34)
    assert results["months"]["months_covered"] == 2


def test_expenses_filters(run_cli, tmp_path):
    ledger = str(tmp_path / "ledger.csv")
    run_cli("expenses", "--file", ledger, "add", "--amount", "100",
            "--description", "a", "--category", "food", "--date", "2026-01-05")
    run_cli("expenses", "--file", ledger, "add", "--amount", "200",
            "--description", "b", "--category", "rent", "--date", "2026-02-05", "--recurring")
    code, out, _ = run_cli("expenses", "--file", ledger, "report",
                           "--category", "rent", "--json")
    assert json.loads(out)["results"]["total_spent"] == 200.0
    code, out, _ = run_cli("expenses", "--file", ledger, "report",
                           "--since", "2026-02-01", "--json")
    assert json.loads(out)["results"]["total_spent"] == 200.0
    code, out, _ = run_cli("expenses", "--file", ledger, "report",
                           "--recurring-only", "--json")
    assert json.loads(out)["results"]["recurring_share"] == 1.0


def test_expenses_needs_an_action(run_cli, tmp_path):
    code, out, err = run_cli("expenses", "--file", str(tmp_path / "l.csv"))
    assert code != 0
    assert "add, list or report" in (out + err)


def test_expenses_rejects_a_file_that_is_not_a_ledger(run_cli, tmp_path):
    path = tmp_path / "notaledger.csv"
    path.write_text("foo,bar\n1,2\n")
    code, out, err = run_cli("expenses", "--file", str(path), "report")
    assert code != 0
    assert "not a finplan ledger" in (out + err)


def test_expenses_missing_file_is_reported_cleanly(run_cli, tmp_path):
    code, out, err = run_cli("expenses", "--file", str(tmp_path / "nope.csv"), "report")
    assert code != 0
    assert "no such file" in (out + err)


# --------------------------------------------------------------------------
# output plumbing
# --------------------------------------------------------------------------
def test_json_output_is_valid_for_every_command(run_cli, debts_file, budget_file):
    invocations = [
        ["mortgage", "--balance", "300000", "--rate", "6", "--term", "30",
         "--start-date", "2026-01-31"],
        ["refinance", "--balance", "268000", "--rate", "6.75", "--remaining-term", "24",
         "--new-rate", "5.5", "--new-term", "30", "--closing-costs", "6500"],
        ["debt", "--balance", "5400", "--rate", "22.9", "--payment", "200"],
        ["debt-plan", "--file", debts_file, "--extra", "300"],
        ["invest", "--initial", "10000", "--contribution", "500", "--years", "20",
         "--return", "7"],
        ["retire", "--current-age", "40", "--retirement-age", "65",
         "--current-savings", "100000", "--monthly-contribution", "1000"],
        ["savings", "--goal", "40000", "--contribution", "800"],
        ["emergency-fund", "--monthly-expenses", "4200", "--current-fund", "9000",
         "--monthly-contribution", "600"],
        ["budget", "--file", budget_file, "--income", "7200"],
        ["paychecks", "--first-payday", "2026-01-02", "--year", "2026"],
        ["networth", "--account", "Cash=1000"],
    ]
    for argv in invocations:
        code, out, err = run_cli(*argv, "--json")
        assert code == 0, f"{argv[0]} failed: {err}"
        payload = json.loads(out)
        assert payload["title"] and isinstance(payload["results"], dict), argv[0]


def test_csv_export_writes_plain_numbers_not_formatted_strings(run_cli, tmp_path):
    path = tmp_path / "out.csv"
    run_cli("mortgage", "--balance", "300000", "--rate", "6", "--term", "30",
            "--start-date", "2026-01-31", "--csv", str(path), "--quiet")
    body = path.read_text()
    assert "$" not in body
    assert "1798.65" in body


def test_quiet_suppresses_the_report(run_cli, tmp_path):
    path = tmp_path / "out.csv"
    code, out, _ = run_cli("mortgage", "--balance", "300000", "--rate", "6", "--term", "30",
                           "--start-date", "2026-01-31", "--csv", str(path), "--quiet")
    assert code == 0
    assert out == ""


def test_detail_includes_the_table(run_cli):
    argv = ["mortgage", "--balance", "300000", "--rate", "6", "--term", "30",
            "--start-date", "2026-01-31"]
    _, without, _ = run_cli(*argv)
    _, with_detail, _ = run_cli(*argv, "--detail")
    assert "Amortisation schedule" not in without
    assert "Amortisation schedule" in with_detail
