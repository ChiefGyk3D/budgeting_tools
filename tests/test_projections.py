"""Tests for the projection commands: invest, retire and refinance."""

import pytest


def test_invest_matches_the_closed_form_for_a_flat_contribution(run_json):
    from decimal import Decimal

    from finplan.core.money import money
    from finplan.core.rates import Frequency, as_rate, periodic_rate
    from finplan.core.tvm import future_value

    results = run_json("invest", "--initial", "10000", "--contribution", "500",
                       "--years", "20", "--return", "7", "--nominal-rate")
    rate = periodic_rate(as_rate(7), Frequency.MONTHLY)
    expected = money(future_value(rate, 240, Decimal("500"), Decimal("10000")))
    assert results["result"]["ending_balance"] == pytest.approx(float(expected), abs=0.05)


def test_invest_nominal_and_effective_conventions_differ(run_json):
    """The two original scripts silently used different conventions."""
    nominal = run_json("invest", "--initial", "10000", "--years", "30",
                       "--return", "7", "--nominal-rate")
    effective = run_json("invest", "--initial", "10000", "--years", "30",
                         "--return", "7", "--effective-rate")
    assert nominal["result"]["ending_balance"] > effective["result"]["ending_balance"]


def test_invest_fees_reduce_the_outcome(run_json):
    base = ["invest", "--initial", "10000", "--contribution", "500",
            "--years", "30", "--return", "7"]
    without = run_json(*base)
    with_fees = run_json(*base, "--fees", "0.75")
    assert with_fees["result"]["ending_balance"] < without["result"]["ending_balance"]
    assert with_fees["net_return"] == pytest.approx(0.0625)


def test_invest_inflation_restates_in_todays_dollars(run_json):
    results = run_json("invest", "--initial", "10000", "--contribution", "500",
                       "--years", "25", "--return", "7", "--inflation", "3")
    result = results["result"]
    assert result["ending_balance_in_today_s_dollars"] < result["ending_balance"]
    assert results["result"]["real_return"] < 0.07


def test_invest_growing_contribution_beats_a_flat_one(run_json):
    base = ["invest", "--contribution", "500", "--years", "25", "--return", "7"]
    flat = run_json(*base)
    growing = run_json(*base, "--contribution-growth", "3")
    assert growing["result"]["total_contributed"] > flat["result"]["total_contributed"]
    assert growing["result"]["ending_balance"] > flat["result"]["ending_balance"]


def test_invest_contribute_at_start_earns_more(run_json):
    base = ["invest", "--contribution", "500", "--years", "10", "--return", "7"]
    assert (
        run_json(*base, "--contribute-at-start")["result"]["ending_balance"]
        > run_json(*base)["result"]["ending_balance"]
    )


def test_invest_rejects_fees_larger_than_the_return(run_cli):
    code, out, err = run_cli("invest", "--contribution", "500", "--years", "10",
                             "--return", "5", "--fees", "99")
    # 5% - 99% is below -100%, which cannot compound.
    assert code != 0 or "ending_balance" not in out


def test_retire_annual_spending_target_uses_the_withdrawal_rate(run_json):
    results = run_json("retire", "--current-age", "40", "--retirement-age", "65",
                       "--current-savings", "100000", "--annual-spending", "80000",
                       "--withdrawal-rate", "4", "--inflation", "0")
    # With no inflation, a $80k income at 4% needs $2,000,000.
    assert results["target"]["needed_at_age_65"] == pytest.approx(2000000, abs=1)


def test_retire_other_income_reduces_the_target(run_json):
    base = ["retire", "--current-age", "40", "--retirement-age", "65",
            "--current-savings", "100000", "--annual-spending", "80000", "--inflation", "0"]
    without = run_json(*base)
    with_pension = run_json(*base, "--other-income", "30000")
    assert with_pension["target"]["needed_at_age_65"] < without["target"]["needed_at_age_65"]


def test_retire_rejects_both_goal_flags(run_cli):
    code, out, err = run_cli("retire", "--current-age", "40", "--retirement-age", "65",
                             "--target", "1000000", "--annual-spending", "80000")
    assert code != 0
    assert "not both" in (out + err)


def test_retire_rejects_a_life_expectancy_before_retirement(run_cli):
    code, out, err = run_cli("retire", "--current-age", "40", "--retirement-age", "65",
                             "--life-expectancy", "60", "--monthly-contribution", "500")
    assert code != 0
    assert "life-expectancy" in (out + err)


def test_refinance_break_even(run_json):
    results = run_json("refinance", "--balance", "268000", "--rate", "6.75",
                       "--remaining-term", "24", "--new-rate", "5.5", "--new-term", "24",
                       "--closing-costs", "6500")
    assert results["change_in_payment"] < 0
    assert results["break_even"]["payments_to_recover_costs"] > 0
    assert results["interest_over_the_life_of_the_loan"]["interest_saved"] > 0


def test_refinance_warns_when_the_term_is_extended(run_cli):
    code, out, _ = run_cli("refinance", "--balance", "268000", "--rate", "6.75",
                           "--remaining-term", "24", "--new-rate", "5.5",
                           "--new-term", "30", "--closing-costs", "6500")
    assert code == 0
    assert "6 years longer" in out
    assert "If you refinance but keep paying the old amount" in out


def test_refinance_rolling_costs_in_needs_no_cash(run_json):
    results = run_json("refinance", "--balance", "268000", "--rate", "6.75",
                       "--remaining-term", "24", "--new-rate", "5.5", "--new-term", "24",
                       "--closing-costs", "6500", "--roll-costs-in")
    assert results["cash_needed_at_closing"] == 0.0
    assert results["new_loan_amount"] == 274500.0


def test_refinance_at_a_higher_rate_never_breaks_even(run_cli):
    code, out, _ = run_cli("refinance", "--balance", "268000", "--rate", "5.5",
                           "--remaining-term", "24", "--new-rate", "7", "--new-term", "24",
                           "--closing-costs", "6500")
    assert code == 0
    assert "never" in out


def test_emergency_fund_coverage_and_stability_guidance(run_json, run_cli):
    results = run_json("emergency-fund", "--monthly-expenses", "4200", "--months", "6",
                       "--current-fund", "9000", "--monthly-contribution", "600")
    assert results["target"] == 25200.0
    assert results["still_to_save"] == 16200.0
    assert results["building_it"]["months_to_fully_funded"] > 0

    code, out, _ = run_cli("emergency-fund", "--monthly-expenses", "4200", "--months", "3",
                           "--income-stability", "self-employed")
    assert "12-month cushion" in out


def test_emergency_fund_warns_without_a_contribution(run_cli):
    code, out, _ = run_cli("emergency-fund", "--monthly-expenses", "4200",
                           "--current-fund", "1000")
    assert code == 0
    assert "the gap never closes" in out


def test_emergency_fund_fully_funded(run_json):
    results = run_json("emergency-fund", "--monthly-expenses", "1000", "--months", "6",
                       "--current-fund", "10000")
    assert results["status"] == "fully funded"
    assert results["amount_above_target"] == 4000.0
