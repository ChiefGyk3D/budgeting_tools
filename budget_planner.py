import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--income', type=float, required=True, help='Monthly income')
parser.add_argument('--investments', type=float, required=True, help='Monthly investment amount')
parser.add_argument('--rainy_day', type=float, required=True, help='Monthly amount set aside for emergencies')
parser.add_argument('--work_gas', type=float, required=True, help='Monthly gas cost for work')
parser.add_argument('--student_loans', type=float, required=True, help='Monthly student loan payment')
parser.add_argument('--alarm', type=float, required=True, help='Monthly alarm cost')
parser.add_argument('--dog_insurance', type=float, required=True, help='Monthly dog insurance cost')
parser.add_argument('--car_insurance', type=float, required=True, help='Monthly car insurance payment')
parser.add_argument('--internet', type=float, required=True, help='Monthly internet bill')
parser.add_argument('--gas', type=float, required=True, help='Monthly gas bill')
parser.add_argument('--electric', type=float, required=True, help='Monthly electric bill')
parser.add_argument('--water', type=float, required=True, help='Monthly water bill')
parser.add_argument('--cell_phone', type=float, required=True, help='Monthly cell phone bill')
parser.add_argument('--mortgage', type=float, required=True, help='Monthly mortgage payment')
parser.add_argument('--house_insurance', type=float, required=True, help='Monthly house insurance payment')
parser.add_argument('--life_insurance', type=float, required=True, help='Monthly life insurance payment')
parser.add_argument('--property_taxes', type=float, required=True, help='Monthly property tax amount')
parser.add_argument('--other', type=float, required=True, help='Other monthly expenses')
args = parser.parse_args()

# Calculate remaining balance
remaining_balance = args.income - args.investments - args.rainy_day - args.work_gas - args.student_loans - args.alarm - args.dog_insurance - args.car_insurance - args.internet - args.gas - args.electric - args.water - args.cell_phone - args.mortgage - args.house_insurance - args.life_insurance - args.property_taxes - args.other

# Print out the remaining balance
print(f'Your remaining balance after all expenses is: ${remaining_balance:.2f}')
