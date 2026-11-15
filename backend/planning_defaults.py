"""Editable planning drafts from dated observations, never automatic confirmation."""
from decimal import Decimal, ROUND_DOWN

from .data_coach import complete_windows, in_window, recorded_balances, total_amount
from .financial import money, spending_rows


def planning_defaults(customer, horizon_days=30):
    windows = complete_windows(customer, 'month')[-3:]
    balance = recorded_balances(customer)
    amount = balance['simultaneous_total_eur']
    if amount is not None and (amount < 0 or any(a['status'] == 'future_dated' for a in balance['accounts'])):
        amount = None
    dates = (f"{windows[0].start_time:%d %b %Y} to {windows[-1].end_time:%d %b %Y}"
             if windows else 'no complete recorded months')
    rows = customer.get_transactions()
    salary = rows[(rows.tx_amount_eur > 0) & rows.transaction_type.isin({'salary', 'salary_payment'})]
    outgoing = spending_rows(customer)
    groceries = outgoing[(outgoing.transaction_type == 'purchase')
                         & outgoing.category.fillna('').str.strip().str.casefold().isin({'groceries', 'grocery'})]

    def estimate(selected, sign=-1):
        groups = [in_window(selected, window) for window in windows]
        if not groups or not any(len(group) for group in groups):
            return None
        average = sum((total_amount(group, sign) for group in groups), Decimal(0)) / len(windows)
        return float(money(average * Decimal(horizon_days) / 30))

    items = [
        {'label': 'Housing payments (such as rent)',
         'amount_eur': estimate(outgoing[outgoing.transaction_type == 'housing_payment'])},
        {'label': 'Utilities (such as electricity)',
         'amount_eur': estimate(outgoing[outgoing.transaction_type == 'utilities_payment'])},
        {'label': 'Food shopping', 'amount_eur': estimate(groceries)},
    ]
    total = (float(sum((money(item['amount_eur']) for item in items), Decimal(0)))
             if all(item['amount_eur'] is not None for item in items) else None)
    monthly_groups = [in_window(outgoing, window) for window in windows]
    monthly = (sum((total_amount(group) for group in monthly_groups), Decimal(0)) / len(windows)
               if windows and any(len(group) for group in monthly_groups) else None)
    # Remove the exact rows included in housing, utilities and food, not a second rounded monetary deduction.
    other = outgoing[(outgoing.transaction_type == 'purchase') & ~outgoing.index.isin(groceries.index)]
    other_groups = [in_window(other, window) for window in windows]
    other_monthly = (sum((total_amount(group) for group in other_groups), Decimal(0)) / len(windows)
                     if monthly is not None else None)
    reserve_options = []
    for months in range(1, 13):
        target = money(monthly * months) if monthly is not None else None
        reserve_options.append({'months': months, 'amount_eur': float(target) if target is not None else None,
                                'exceeds_balance': target > money(amount) if target is not None and amount is not None else None})
    return {
        'everyday': {'amount_eur': float(money(other_monthly * horizon_days / 30)) if other_monthly is not None else None,
                     'daily_average_eur': float(money(other_monthly / 30)) if other_monthly is not None else None,
                     'note': ('Average remaining purchases after excluding housing, utilities and food already listed above. '
                              'Uses a 30-day month; the plan total is calculated before rounding the displayed daily average. '
                              'If your edited bills total includes other daily costs, remove those from this amount too.')},
        'reserve': {'monthly_expenses_eur': float(money(monthly)) if monthly is not None else None,
                    'default_months': 3, 'options': reserve_options,
                    'note': ('Start with 3 months of average expenses, within your chosen 2–4 month range. '
                             'Choose 1–12 months or enter your own amount. This is a suggested target, not money already saved. '
                             'If it exceeds your balance, build towards it or choose an amount you can protect now.')},
        'horizon_days': horizon_days,
        'balance': {'amount_eur': amount, 'recorded_at': balance['total_recorded_at'],
                    'note': ('Latest recorded balance, not a live balance. Review its date before using this demo plan.'
                             if amount is not None else 'A usable combined balance is unavailable in the latest account records.')},
        'income': {'amount_eur': estimate(salary, 1),
                   'note': (f'Salary average from {dates}, adjusted to {horizon_days} days using a 30-day month. '
                            'This estimates additional income after the starting balance, not salary already received. '
                            'Change it to the amount you expect to receive; actual pay dates may differ.')},
        'bills': {'items': items, 'total_eur': total,
                  'note': (f'Averages from {dates}, adjusted to {horizon_days} days using a 30-day month. '
                           'Housing and utilities may include more than rent and electricity. Missing amounts are unknown, not zero. '
                           'Edit the total for unpaid bills and food you expect, including any other costs. '
                           'Do not count these costs again under everyday spending.')},
        'note': ('Suggested starting amounts only. Past records may be incomplete and do not confirm future income or bills. '
                 'Review and confirm before using them for goal or spending estimates.'),
    }


def income_remainder(confirmed_income_eur=None, upcoming_essential_bills_eur=None,
                     everyday_spending_eur=None, voluntary_goal_contribution_eur=None, horizon_days=30):
    required = (confirmed_income_eur, upcoming_essential_bills_eur, everyday_spending_eur)
    included = voluntary_goal_contribution_eur is not None
    remaining = None
    if all(value is not None for value in required):
        remaining = (money(confirmed_income_eur) - money(upcoming_essential_bills_eur)
                     - money(everyday_spending_eur) - money(voluntary_goal_contribution_eur or 0))
    daily = (max(remaining, Decimal(0)) / horizon_days).quantize(Decimal('0.01'), rounding=ROUND_DOWN) if remaining is not None else None
    return {'daily_eur': float(daily) if daily is not None else None,
            'weekly_eur': float(min(max(remaining, Decimal(0)), daily * 7)) if daily is not None else None,
            'usage_status': 'unavailable', 'spent_today_eur': None, 'spent_this_week_eur': None,
            'remaining_income_eur': float(remaining) if remaining is not None else None,
            'goal_contribution_included': included,
            'note': ('After your entered goal contribution. ' if included else 'Before choosing a goal contribution. ')
                    + 'Income only: your existing balance and protected emergency money are not included. '
                    'This is not a safe-to-spend estimate. A negative amount means these planned outgoings exceed this income.'}


def spending_plan_target(assumptions, period):
    explicit = assumptions.get('weekly_budget_eur' if period == 'week' else 'monthly_budget_eur')
    if explicit is not None:
        return float(money(explicit))
    bills, everyday = assumptions.get('upcoming_essential_bills_eur'), assumptions.get('everyday_spending_eur')
    if bills is None or everyday is None:
        return None
    days = assumptions['horizon_days']
    return float(money((money(bills) + money(everyday)) * (7 if period == 'week' else 30) / days))
