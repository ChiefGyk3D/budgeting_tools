import argparse
import csv
import datetime

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--amount', type=float, required=True, help='Expense amount')
parser.add_argument('--description', type=str, required=True, help='Expense description')
parser.add_argument('--recurring', action='store_true', help='Mark expense as recurring')
args = parser.parse_args()

# Open the CSV file (or create it if it doesn't exist)
with open('expenses.csv', 'a', newline='') as file:
    writer = csv.writer(file)
    
    # Get the current date
    date = datetime.datetime.now().date()
    
    # Write the expense data to the CSV file
    writer.writerow([date, args.amount, args.description, args.recurring])
