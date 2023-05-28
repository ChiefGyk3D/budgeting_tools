import argparse
import datetime
import math
import csv
from dateutil.relativedelta import relativedelta

# Define the calculate_interest_and_payments function
def calculate_interest_and_payments(principal, monthly_interest_rate, payment_amount, extra_payment):
    total_interest = 0
    number_of_payments = 0
    last_payment_amount = 0
    while principal > 0:
        interest_payment = principal * monthly_interest_rate
        principal_payment = payment_amount - interest_payment
        principal -= principal_payment + extra_payment
        if principal < 0:
            principal_payment += principal
            extra_payment += principal
            principal = 0
        last_payment_amount = principal_payment + interest_payment + extra_payment
        total_interest += interest_payment
        number_of_payments += 1
    return total_interest, number_of_payments, last_payment_amount


# Calculate payoff date
def calculate_payoff_date(start_date, remaining_principal, monthly_interest_rate, payment_amount, extra_payment, payments_per_year, biweekly):
    i = 0
    while remaining_principal > 0:
        i += 1
        if biweekly:
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
            remaining_principal = 0
    last_payment_amount = principal_payment + interest_payment + extra_payment
    payment_date -= datetime.timedelta(days=((payment_amount - last_payment_amount) / payment_amount)*30)
    return payment_date

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

# Convert start date string to a datetime object
start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d').date()

# Calculate how many payments have already been made
if args.biweekly:
    payments_made = relativedelta(datetime.date.today(), start_date).years * 26 + relativedelta(datetime.date.today(), start_date).months * 2
else:
    payments_made = relativedelta(datetime.date.today(), start_date).years * 12 + relativedelta(datetime.date.today(), start_date).months

# Calculate the principal paid so far
principal_paid = original_principal - remaining_principal

# Calculate the interest paid so far
interest_paid_so_far = payments_made * payment_amount - principal_paid

# Calculate total interest and number of payments for the original loan terms, and subtract the payments already made
original_total_interest, original_number_of_payments, _ = calculate_interest_and_payments(original_principal, monthly_interest_rate, payment_amount, 0)
original_total_interest -= interest_paid_so_far
original_number_of_payments -= payments_made

# Calculate total interest and number of payments for the adjusted loan terms, and subtract the payments already made
adjusted_total_interest, adjusted_number_of_payments, _ = calculate_interest_and_payments(remaining_principal, monthly_interest_rate, payment_amount, extra_payment)
adjusted_total_interest -= interest_paid_so_far
adjusted_number_of_payments -= payments_made

# Calculate the interest and number of payments saved
interest_saved = original_total_interest - adjusted_total_interest
payments_saved = original_number_of_payments - adjusted_number_of_payments

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

# Calculate total interest and number of future payments for the original loan terms
future_original_total_interest, future_original_number_of_payments, _ = calculate_interest_and_payments(remaining_principal, monthly_interest_rate, payment_amount, 0)

# Calculate total interest and number of future payments for the adjusted loan terms
future_adjusted_total_interest, future_adjusted_number_of_payments, _ = calculate_interest_and_payments(remaining_principal, monthly_interest_rate, payment_amount, extra_payment)

# Calculate the interest and number of payments saved
interest_saved = future_original_total_interest - future_adjusted_total_interest
payments_saved = future_original_number_of_payments - future_adjusted_number_of_payments

# Calculate the expected end date of the mortgage at the time of loan origination
expected_end_date = start_date + relativedelta(years=term_years)

# Initialize a list to store the payment schedule
payment_schedule = []

from dateutil.relativedelta import relativedelta

# Calculate the payment schedule
payment_date = start_date
for i in range(1, total_payments + 1):
    # Calculate the payment date
    if args.biweekly:
        payment_date += relativedelta(weeks=+2)
    else:
        payment_date += relativedelta(months=+1)

    interest_payment = remaining_principal * monthly_interest_rate
    principal_payment = payment_amount - interest_payment
    remaining_principal -= principal_payment + extra_payment
    payoff_date = calculate_payoff_date(start_date, remaining_principal, monthly_interest_rate, payment_amount, extra_payment, payments_per_year, payments_made, args.biweekly)

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
        print(f"Expected End Date: {expected_end_date}")
        print(f"Extra Payment: ${payment_schedule[-1]['Extra Payment']:.2f}")
        print(f"Remaining Principal: ${payment_schedule[-1]['Remaining Principal']:.2f}")
        print(f"Estimated Payoff Date: {payoff_date}")
        print(f"Original Total Interest: {original_total_interest}, Adjusted Total Interest: {adjusted_total_interest}")
        print(f"Original Number of Payments: {original_number_of_payments}, Adjusted Number of Payments: {adjusted_number_of_payments}")
        print(f"Total Interest Saved: ${interest_saved:.2f}")
        print(f"Number of Payments Saved: {payments_saved}")
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
