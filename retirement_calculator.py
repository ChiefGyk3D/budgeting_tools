import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--current-age', type=int, required=True, help='Your current age')
parser.add_argument('--retirement-age', type=int, required=True, help='Your retirement age')
parser.add_argument('--current-savings', type=float, required=True, help='Your current savings')
parser.add_argument('--retirement-savings', type=float, required=True, help='Your desired retirement savings')
parser.add_argument('--annual-return', type=float, default=0.05, help='Annual rate of return (as a percentage, default is 5%)')
args = parser.parse_args()

current_age = args.current_age
retirement_age = args.retirement_age
current_savings = args.current_savings
retirement_savings = args.retirement_savings
annual_return = args.annual_return / 100  # Convert annual return from percentage to decimal

# Calculate the number of years until retirement
years_until_retirement = retirement_age - current_age

# Calculate the number of months until retirement
months_until_retirement = years_until_retirement * 12

# Calculate the monthly rate of return
monthly_return = (1 + annual_return) ** (1/12) - 1

# Calculate the future value of the current savings
future_value_current_savings = current_savings * (1 + monthly_return) ** months_until_retirement

# Calculate the monthly contribution needed to reach the retirement savings goal
monthly_contribution = (retirement_savings - future_value_current_savings) / (((1 + monthly_return) ** months_until_retirement - 1) / monthly_return)

print(f'To reach your retirement savings goal, you need to save ${monthly_contribution:.2f} per month.')
