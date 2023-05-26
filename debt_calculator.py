import argparse
import math

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--principal', type=float, required=True, help='Principal amount')
parser.add_argument('--interest-rate', type=float, required=True, help='Annual interest rate (as a percentage)')
parser.add_argument('--monthly-payment', type=float, required=True, help='Monthly payment')
args = parser.parse_args()

principal = args.principal
interest_rate = args.interest_rate / 100 / 12  # Convert annual interest rate from percentage to monthly rate
monthly_payment = args.monthly_payment

# Calculate the number of payments required to pay off the debt
num_payments = -math.log(1 - (interest_rate * principal / monthly_payment)) / math.log(1 + interest_rate)

# Convert the number of payments to years and months
years = num_payments // 12
months = num_payments % 12

print(f'It will take approximately {years} years and {months} months to pay off the debt.')
