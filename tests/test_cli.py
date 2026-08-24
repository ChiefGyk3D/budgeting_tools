"""End-to-end tests, including one per bug found in the original scripts."""

import datetime as dt

import pytest

from finplan.cli import build_parser, main


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    for command in (
        "budget", "expenses", "paychecks", "savings", "emergency-fund", "debt",
        "debt-plan", "mortgage", "refinance", "invest", "retire", "networth",
    ):
        assert command in out


def test_no_command_prints_help_and_fails(capsys):
    assert main([]) == 1
    assert "usage: finplan" in capsys.readouterr().out


def test_every_command_has_a_runnable_parser():
    parser = build_parser()
    actions = [a for a in parser._actions if a.dest == "command"]
    assert actions and actions[0].choices


# --------------------------------------------------------------------------
# mortgage
# --------------------------------------------------------------------------
MORTGAGE = [
    "mortgage", "--balance", "300000", "--rate", "6", "--term", "30",
    "--start-date", "2026-01-31",
]


def test_mortgage_month_end_start_date_does_not_crash(run_json):
    """mortgage_calculator.py raised ValueError for any 29th-31st loan."""
    results = run_json(*MORTGAGE)
    assert results["payoff"]["payments_remaining"] == 360
    assert results["scheduled_payment_per_month"] == 1798.65


def test_mortgage_csv_contains_the_whole_schedule(run_cli, tmp_path):
    """The original stopped at the first future payment and wrote a truncated file."""
    path = tmp_path / "schedule.csv"
    code, _, _ = run_cli(*MORTGAGE, "--csv", str(path), "--quiet")
    assert code == 0
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 361  # header + 360 payments
    assert lines[-1].startswith("360,")
    assert lines[-1].endswith("0.00,347515.44") or "0.00," in lines[-1]


def test_mortgage_reports_extra_payment_savings(run_json):
    results = run_json(*MORTGAGE, "--extra-payment", "300")
    effect = results["effect_of_extra_payments"]
    assert effect["interest_saved"] > 100000
    assert effect["payments_saved"] > 100


def test_mortgage_biweekly_beats_monthly(run_json):
    monthly = run_json(*MORTGAGE)
    biweekly = run_json(*MORTGAGE, "--frequency", "biweekly")
    assert biweekly["payoff"]["total_interest"] < monthly["payoff"]["total_interest"]
    assert biweekly["effect_of_biweekly_payments"]["interest_saved"] > 0


def test_mortgage_pmi_requires_a_property_value(run_cli):
    code, out, err = run_cli(*MORTGAGE, "--pmi", "150")
    assert code != 0
    assert "--property-value" in (out + err)


def test_mortgage_flags_a_balance_inconsistent_with_the_contract(run_cli):
    code, out, _ = run_cli(
        "mortgage", "--balance", "295000", "--original-principal", "300000",
        "--rate", "6", "--term", "30", "--start-date", "2026-09-01",
        "--origination-date", "2021-04-30",
    )
    assert code == 0
    assert "does not match the others" in out


def test_mortgage_rejects_a_non_amortising_payment(run_cli):
    code, out, err = run_cli(*MORTGAGE, "--payment", "100")
    assert code != 0
    assert "never amortises" in (out + err)


# --------------------------------------------------------------------------
# debt
# --------------------------------------------------------------------------
def test_debt_payment_below_interest_is_a_clear_error(run_cli):
    """debt_calculator.py died with 'ValueError: math domain error'."""
    code, out, err = run_cli("debt", "--balance", "5400", "--rate", "22.9", "--payment", "50")
    assert code != 0
    message = out + err
    assert "does not cover" in message
    assert "math domain" not in message


def test_debt_reports_whole_periods_not_fractions(run_json):
    """The original printed '5.0 years and 3.4 months'."""
    results = run_json("debt", "--balance", "5400", "--rate", "22.9", "--payment", "200")
    assert isinstance(results["payments_to_clear"], int)
    assert "." not in results["time_to_clear"]


def test_debt_solves_for_a_required_payment(run_json):
    results = run_json("debt", "--balance", "5400", "--rate", "22.9", "--payoff-in", "24")
    assert results["payments_to_clear"] == 24
    assert 280 < results["required_payment_per_month"] < 300


def test_debt_accepts_the_legacy_flag_names(run_json):
    results = run_json(
        "debt", "--principal", "5400", "--interest-rate", "22.9", "--monthly-payment", "200"
    )
    assert results["payments_to_clear"] == 39


# --------------------------------------------------------------------------
# retirement
# --------------------------------------------------------------------------
def test_retirement_default_return_is_seven_percent_not_seven_hundredths(run_json):
    """retirement_calculator.py had default=0.05 then divided by 100."""
    results = run_json(
        "retire", "--current-age", "40", "--retirement-age", "65",
        "--current-savings", "100000", "--monthly-contribution", "1000",
    )
    assert results["assumed_return"] == pytest.approx(0.07)


def test_retirement_rejects_a_zero_horizon(run_cli):
    """The original divided by zero here."""
    code, out, err = run_cli(
        "retire", "--current-age", "65", "--retirement-age", "65",
        "--current-savings", "100000", "--monthly-contribution", "500",
    )
    assert code != 0
    assert "must be greater than" in (out + err)
    assert "ZeroDivision" not in (out + err)


def test_retirement_says_no_contribution_needed_when_already_on_track(run_cli):
    """The original printed a negative monthly saving instruction."""
    code, out, _ = run_cli(
        "retire", "--current-age", "40", "--retirement-age", "65",
        "--current-savings", "2000000", "--target", "1000000",
    )
    assert code == 0
    assert "none" in out
    assert "-$" not in out.split("Required monthly contribution")[-1].splitlines()[0]


def test_retirement_reports_a_shortfall(run_json):
    results = run_json(
        "retire", "--current-age", "40", "--retirement-age", "65",
        "--current-savings", "50000", "--monthly-contribution", "300",
        "--target", "2000000",
    )
    assert results["target"]["shortfall_at_retirement"] > 0
    assert results["target"]["extra_needed_each_month"] > 0


# --------------------------------------------------------------------------
# savings
# --------------------------------------------------------------------------
def test_savings_zero_contribution_is_rejected(run_cli):
    """savings_goal_tracker.py raised ZeroDivisionError."""
    code, out, err = run_cli("savings", "--goal", "1000", "--contribution", "0")
    assert code != 0
    assert "ZeroDivision" not in (out + err)


def test_savings_accounts_for_interest(run_json):
    """The original ignored interest entirely."""
    without = run_json("savings", "--goal", "40000", "--current-savings", "12000",
                       "--contribution", "800")
    with_interest = run_json("savings", "--goal", "40000", "--current-savings", "12000",
                             "--contribution", "800", "--apy", "4.5")
    assert with_interest["at_your_current_pace"]["periods_to_goal"] < (
        without["at_your_current_pace"]["periods_to_goal"]
    )
    assert with_interest["at_your_current_pace"]["interest_earned"] > 0


def test_savings_already_met_goal(run_json):
    results = run_json("savings", "--goal", "1000", "--current-savings", "1500",
                       "--contribution", "100")
    assert results["status"] == "goal already reached"
    assert results["amount_over_the_goal"] == 500.0


def test_savings_solves_for_a_deadline(run_json):
    results = run_json("savings", "--goal", "40000", "--current-savings", "12000",
                       "--by-date", "2029-01-01", "--as-of", "2026-08-21")
    assert results["to_hit_the_deadline"]["contribution_needed_per_month"] > 0


# --------------------------------------------------------------------------
# paychecks
# --------------------------------------------------------------------------
def test_paychecks_finds_the_three_paycheck_months(run_json):
    results = run_json("paychecks", "--first-payday", "2026-01-02", "--year", "2026")
    assert results["paydays_in_window"] == 26
    extra = results["months_with_more_than_2_paychecks"]
    assert set(extra) == {"january_2026", "july_2026"}


def test_paychecks_handles_a_27_payday_year(run_json):
    """biweekly_pay.py hardcoded range(26)."""
    results = run_json("paychecks", "--first-payday", "2032-01-01", "--year", "2032")
    assert results["paydays_in_window"] == 27


def test_paychecks_does_not_merge_the_same_month_of_different_years(run_json):
    """The original keyed the tally on the month NAME, so the two Januaries in a
    window merged into one bucket of six paydays."""
    results = run_json(
        "paychecks", "--first-payday", "2026-01-02", "--through", "2027-06-30"
    )
    extra = results["months_with_more_than_2_paychecks"]
    # Both Januaries appear, separately, each with its own paydays.
    assert "january_2026" in extra and "january_2027" in extra
    assert extra["january_2026"] != extra["january_2027"]
    assert extra["january_2026"].startswith("3 paychecks")
    assert extra["january_2027"].startswith("3 paychecks")


def test_paychecks_anchor_need_not_be_the_first_payday_of_the_year(run_json):
    from_january = run_json("paychecks", "--first-payday", "2026-01-02", "--year", "2026")
    from_july = run_json("paychecks", "--first-payday", "2026-07-17", "--year", "2026")
    assert from_july["paydays_in_window"] == from_january["paydays_in_window"]
    assert from_july["first_payday"] == from_january["first_payday"]


def test_paychecks_rejects_a_non_payroll_frequency(run_cli):
    code, out, err = run_cli("paychecks", "--first-payday", "2026-01-02", "--frequency", "daily")
    assert code != 0
    assert "not a payroll frequency" in (out + err)


def test_group_by_month_keys_on_year_and_month():
    """Direct check on the grouping the original got wrong."""
    from finplan.commands.paychecks import group_by_month

    dates = [dt.date(2026, 1, 2), dt.date(2026, 1, 16), dt.date(2027, 1, 1)]
    buckets = group_by_month(dates)
    assert set(buckets) == {(2026, 1), (2027, 1)}
    assert len(buckets[(2026, 1)]) == 2
    assert len(buckets[(2027, 1)]) == 1
