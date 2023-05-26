# Biweekly Paycheck Calculator

This script calculates the months in which you will receive three paychecks, assuming you are paid every two weeks.

The script takes your initial payday as input and calculates paydays for one year (26 pay periods). The dates are stored in a dictionary, which is then used to determine the months in which three paydays occur.

## Usage

The script uses command-line arguments to take input from the user.

To run the script, use the following format:

```
python paycheck_calculator.py --pay-date YYYY-MM-DD
```

Replace YYYY-MM-DD with the date of your first paycheck in the format of Year-Month-Day. For example, if your first paycheck was on July 1, 2023, you would use:

```
python paycheck_calculator.py --pay-date 2023-07-01
```

The script will then print the names of the months where you would receive three paychecks.

## Dependencies

The script requires Python's built-in modules argparse and datetime.

## Limitations

The script assumes a consistent payment schedule of every two weeks and does not account for holidays or any other exceptions that might cause a payday to be moved. Please adjust based on your specific circumstances.