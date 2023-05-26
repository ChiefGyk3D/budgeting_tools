# Budgeting Tools

This repository contains simple Python scripts to help with personal budgeting and finance calculations.

## Scripts

### Biweekly Paychecks

The Paycheck Calculator script calculates the months in which you will receive three paychecks, assuming you are paid every two weeks.

Usage:

```
python paycheck_calculator.py --pay-date YYYY-MM-DD
```

Replace YYYY-MM-DD with the date of your first paycheck in the format of Year-Month-Day.

### Investment Calculator

The Investment Calculator script calculates the future value of an investment given an initial investment amount, a monthly investment amount, the number of years for the investment, and an annual interest rate.

Usage:

```
python investment_calculator.py --initial-investment X --monthly-investment Y --years Z --interest-rate R
```

Replace X with your initial investment amount, Y with your monthly investment amount, Z with the number of years for the investment, and R with the annual interest rate as a percentage.

### Retirement Planner

This script calculates how much you need to save each month to reach a specified retirement savings goal.

Usage:

```
python3 retirement_planner.py --current-age 31 --retirement-age 65 --current-savings 15000 --retirement-savings 1000000 --annual-return 7
```
This command will calculate how much you need to save each month, starting at age 31 with $15,000 already saved, to have $1,000,000 by the time you retire at age 65, assuming an annual return of 7%.

### Debt Calculator

This script calculates the time to pay off a debt given the principal, interest rate, and monthly payment.

Usage:

```
python3 debt_calculator.py --principal 5000 --interest-rate 5 --monthly-payment 200
```

This command will calculate how long it will take to pay off a $5,000 debt with a 5% annual interest rate, making $200 payments each month.

### Savings Goal Tracker

This script calculates how much money you would need to save per month to meet your savings goal.

Usage:

```
python3 savings_goal_tracker.py --goal 10000 --current-savings 2000 --monthly-contribution 500
```

This command will calculate how many months it will take to reach a savings goal of $10,000, starting with $2,000 and saving $500 per month.

Remember that this script doesn't take into account interest earned on your savings, or any changes in your monthly contributions over time.

### Budget Planner


## Dependencies

The scripts require Python's built-in modules argparse and datetime.

## Limitations

These are simple scripts for personal use and should not be relied upon for financial advice. They do not account for taxes or any changes in your income or investment over time. Always consult with a financial advisor for professional guidance.
Contributing

This is a simple project and not actively maintained, but contributions are welcome. Please open an issue to discuss any changes or improvements.

## Legal Disclaimer

These scripts are simplified and make assumptions. They do not take into account all aspects of personal finance. Please consult with a financial advisor for personalized advice.