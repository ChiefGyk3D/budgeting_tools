import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--goal', type=float, required=True, help='Savings goal')
parser.add_argument('--current-savings', type=float, required=True, help='Current amount saved')
parser.add_argument('--monthly-contribution', type=float, required=True, help='Amount saved each month')
args = parser.parse_args()

goal = args.goal
current_savings = args.current_savings
monthly_contribution = args.monthly_contribution

# Calculate how many months it will take to reach the goal
months_to_goal = (goal - current_savings) / monthly_contribution

# If the current savings is greater than the goal, no months are needed
if months_to_goal < 0:
    months_to_goal = 0

# Print out the number of months
print(f'It will take approximately {round(months_to_goal)} months to reach your savings goal.')
