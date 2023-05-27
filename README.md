# Budgeting Tools

This repository contains simple Python scripts to help with personal budgeting and finance calculations.

## Scripts

### Biweekly Paychecks

The Paycheck Calculator script calculates the months in which you will receive three paychecks, assuming you are paid every two weeks.

Usage:

```
python paycheck_calculator.py --pay-date YYYY-MM-DD
```

Replace YYYY-MM-DD with the date of the first payday of the year.

This script can also output all the pay dates for the entire year to a CSV file:

```
python paycheck_calculator.py --pay-date YYYY-MM-DD --output file_name.csv
```

Replace filename.csv with the desired name for the output CSV file.

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
python3 retirement_planner.py --current-age x --retirement-age y --current-savings z --retirement-savings s --annual-return r
```

Replace X with your current age, Y with your desired retirement age, Z with your current savings amount, S with your desired savings amount at retirement, and R with the estimated annual return rate as a percentage.

### Debt Calculator

This script calculates the time to pay off a debt given the principal, interest rate, and monthly payment.

Usage:

```
python debt_calculator.py --debt X --monthly-payment Y --interest-rate R
```

Replace X with the total debt amount, Y with the amount you can pay monthly, and R with the annual interest rate as a percentage.

### Expense Tracker

This script allows you to record your expenses, with the option to mark an expense as recurring.

Usage:

```
python expense_tracker.py --amount X --description "description" [--recurring]
```

Replace X with the expense amount and description with a brief description of the expense. Add --recurring at the end if the expense is a recurring one.

### Savings Goal Tracker

This script calculates how much money you would need to save per month to meet your savings goal.

Usage:

```
python3 savings_goal_tracker.py --goal X --current-savings Y --monthly-contribution Z
```

Replace X with your savings goal, Y with your current savings, and Z with your monthly contribution. This command will calculate how many months it will take to reach your savings goal.

Remember that this script doesn't take into account interest earned on your savings, or any changes in your monthly contributions over time.

### Budget Planner

This script allows you to plan your monthly budget by specifying the amount you aim to spend in various categories.

Usage:

```
python budget_planner.py --category "category name" --amount X
```

Replace "category name" with the name of the budget category (e.g., groceries, rent, utilities, etc.), and X with the amount you plan to spend in that category. Run this command for each category to add it to your budget. The budget is saved in a file named budget.txt by default.

You can also specify a different file to save your budget:
```
python budget_planner.py --category "category name" --amount X --file "file name"
```

Replace "file name" with the desired name for the budget file.

Please note that this script currently does not have the ability to modify an existing budget. If you need to change a budget, you will have to recreate the entire budget file.


## Dependencies

The scripts require Python's built-in modules argparse, calendar, and datetime.

## Limitations

These are simple scripts for personal use and should not be relied upon for financial advice. They do not account for taxes or any changes in your income or investment over time. Always consult with a financial advisor for professional guidance.

## Contributing

This is a simple project and not actively maintained, but contributions are welcome. Please open an issue to discuss any changes or improvements.

## Legal Disclaimer

These scripts are simplified and make assumptions. They do not take into account all aspects of personal finance. Please consult with a financial advisor for personalized advice.
