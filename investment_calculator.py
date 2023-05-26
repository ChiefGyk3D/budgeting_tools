import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--initial-investment', type=float, required=True, help='Initial investment amount')
parser.add_argument('--monthly-investment', type=float, required=True, help='Amount invested each month')
parser.add_argument('--years', type=int, required=True, help='Number of years for the investment')
parser.add_argument('--interest-rate', type=float, required=True, help='Annual interest rate (as a percentage)')
args = parser.parse_args()

initial_investment = args.initial_investment
monthly_investment = args.monthly_investment
years = args.years
interest_rate = args.interest_rate / 100  # Convert interest rate from percentage to decimal

# Calculate the number of months
months = years * 12

# Calculate the monthly interest rate
monthly_interest_rate = interest_rate / 12

# Calculate the future value of the initial investment
future_value_initial_investment = initial_investment * ((1 + monthly_interest_rate) ** months)

# Calculate the future value of the monthly investments
future_value_monthly_investments = 0
for i in range(months):
    future_value_monthly_investments = (future_value_monthly_investments + monthly_investment) * (1 + monthly_interest_rate)

# Calculate the total future value
future_value = future_value_initial_investment + future_value_monthly_investments

print(f'The future value of the investment is ${future_value:.2f}')
