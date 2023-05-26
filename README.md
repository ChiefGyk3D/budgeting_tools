# Budgeting Tools

This repository contains simple Python scripts to help with personal budgeting and finance calculations.

## Scripts

### 1. Paycheck Calculator

The Paycheck Calculator script calculates the months in which you will receive three paychecks, assuming you are paid every two weeks.

Usage:

```
python paycheck_calculator.py --pay-date YYYY-MM-DD
```

Replace YYYY-MM-DD with the date of your first paycheck in the format of Year-Month-Day.

### 2. Investment Calculator

The Investment Calculator script calculates the future value of an investment given an initial investment amount, a monthly investment amount, the number of years for the investment, and an annual interest rate.

Usage:

```
python investment_calculator.py --initial-investment X --monthly-investment Y --years Z --interest-rate R
```

Replace X with your initial investment amount, Y with your monthly investment amount, Z with the number of years for the investment, and R with the annual interest rate as a percentage.

## Dependencies

The scripts require Python's built-in modules argparse and datetime.

## Limitations

These are simple scripts for personal use and should not be relied upon for financial advice. They do not account for taxes or any changes in your income or investment over time. Always consult with a financial advisor for professional guidance.
Contributing

This is a simple project and not actively maintained, but contributions are welcome. Please open an issue to discuss any changes or improvements.