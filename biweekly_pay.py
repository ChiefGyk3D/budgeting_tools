import argparse
import datetime

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--pay-date', type=str, required=True, help='Pay date (YYYY-MM-DD)')
args = parser.parse_args()

# Convert pay date string to a datetime object
pay_date = datetime.datetime.strptime(args.pay_date, '%Y-%m-%d').date()

# Initialize an empty dictionary to keep track of paychecks per month
paychecks_per_month = {}

for i in range(26):  # For each payday in the year
    # Calculate the date of the current payday
    payday = pay_date + datetime.timedelta(days=14*i)
    
    # Get the month of the current payday
    month = payday.strftime('%B')
    
    # Add the payday to the dictionary
    if month in paychecks_per_month:
        paychecks_per_month[month] += 1
    else:
        paychecks_per_month[month] = 1

# Print the months with three paydays
for month, num_paychecks in paychecks_per_month.items():
    if num_paychecks == 3:
        print(month)