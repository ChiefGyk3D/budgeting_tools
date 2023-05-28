import argparse
import datetime
import math
import csv

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--start-date', type=str, required=True, help='Start date of the loan (YYYY-MM-DD)')
parser.add_argument('--remaining-principal', type=float, required=True, help='Remaining principal on the loan')
parser.add_argument('--original-principal', type=float, required=True, help='Original principal of the loan')
parser.add_argument('--interest-rate', type=float, required=True, help='Annual interest rate (as a percentage)')
parser.add_argument('--term', type=int, required=True, help='Term of the loan in years')
parser.add_argument('--extra-payment', type=float, required=False, default=0, help='Extra payment made each period')
parser.add_argument('--biweekly', action='store_true', help='Make payments every two weeks instead of monthly')
parser.add_argument('--output', type=str, required=False, help='CSV file to write the payment schedule to')
args = parser.parse_args()

# Convert start date string to a datetime object
start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d').date()

# Get the loan details from the arguments
remaining_principal = args.remaining_principal
original_principal = args.original_principal
annual_interest_rate = args.interest_rate / 100  # Convert to a decimal
term_years = args.term
extra_payment = args.extra_payment

# Calculate the number of payments and the payment amount
if args.biweekly:
    payments_per_year = 26
else:
    payments_per_year = 12
total_payments = term_years * payments_per_year
monthly_interest_rate = annual_interest_rate / payments_per_year
payment_amount = (original_principal * monthly_interest_rate) / (1 - (1 + monthly_interest_rate) ** -total_payments)

# Initialize a list to store the payment schedule
payment_schedule = []

# Calculate the payment schedule
for i in range(1, total_payments + 1):
    # Calculate the payment date
    if args.biweekly:
        payment_date = start_date + datetime.timedelta(weeks=2*(i-1))
    else:
        year = start_date.year + ((start_date.month - 1 + i) // 12)
        month = (start_date.month - 1 + i) % 12 + 1
        day = start_date.day
        payment_date = datetime.date(year, month, day)

    interest_payment = remaining_principal * monthly_interest_rate
    principal_payment = payment_amount - interest_payment
    remaining_principal -= principal_payment + extra_payment

    if remaining_principal < 0:
        principal_payment += remaining_principal
        extra_payment += remaining_principal
        remaining_principal = 0

    # Add the payment details to the payment schedule
    payment_schedule.append({
        'Payment Date': payment_date,
        'Payment Number': i,
        'Principal Payment': principal_payment,
        'Interest Payment': interest_payment,
        'Extra Payment': extra_payment,
        'Remaining Principal': remaining_principal
    })
    # Print the next payment schedule if it is in the future
    if payment_date > datetime.date.today():
        print(f"Payment Number: {payment_schedule[-1]['Payment Number']}")
        print(f"Payment Date: {payment_schedule[-1]['Payment Date']}")
        print(f"Principal Payment: ${payment_schedule[-1]['Principal Payment']:.2f}")
        print(f"Interest Payment: ${payment_schedule[-1]['Interest Payment']:.2f}")
        print(f"Extra Payment: ${payment_schedule[-1]['Extra Payment']:.2f}")
        print(f"Remaining Principal: ${payment_schedule[-1]['Remaining Principal']:.2f}")
        break

    # Break the loop if the loan is paid off
    if remaining_principal == 0:
        break

# Write the payment schedule to a CSV file if the --output argument was used
if args.output:
    with open(args.output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=payment_schedule[0].keys())
        writer.writeheader()
        for payment in payment_schedule:
            payment['Payment Date'] = payment['Payment Date'].strftime('%Y-%m-%d')
            payment = {k: '$%.2f' % v if isinstance(v, float) else v for k, v in payment.items()}
            writer.writerow(payment)
