"""Read-only goal scenarios using the same cash-flow policy as Home. No provider calls."""
from decimal import Decimal
from math import ceil

from .automatic_demo_budget import automatic_budget
from .financial import PRIORITIES, money

PRIORITY_LABELS = {'critical': 'Urgent', 'important': 'Important', 'flexible': 'Flexible'}


def goal_plan(customer, goals, as_of=None):
    budget = automatic_budget(customer, goals, as_of, require_goal=False)
    result = {**budget, 'goals': [], 'monthly_savings_capacity_eur': None,
              'additional_savings_if_redirect_extra_eur': budget['monthly_extra_eur'],
              'timing_basis': ('Conditional estimate: the historical monthly saving budget repeats, paid at the end of each '
                               'typical month. Once a goal is funded, its allocation moves to the next goal. '
                               'Targets are remaining amounts; existing savings are unknown. No money or goal is changed.')}
    if budget['status'] != 'estimated':
        result['goals'] = [{'goal_id': g.id, 'name': g.name, 'priority': g.priority,
                            'priority_label': PRIORITY_LABELS[g.priority], 'target_eur': float(g.amount_eur),
                            'monthly_allocation_eur': None, 'completion_months': None, 'completion_weeks': None,
                            'save_all_extra_months': None, 'save_all_extra_weeks': None} for g in
                           sorted(goals, key=lambda g: PRIORITIES[g.priority])]
        return result
    capacity = money(budget['surplus_eur']) - money(budget['reserve_contribution_eur'])
    pool = money(budget['goal_budget_eur'])
    result['monthly_savings_capacity_eur'] = float(capacity)
    allocation = {item['goal_id']: item['allocated_eur'] for item in budget['goal_allocations']}
    cumulative = Decimal(0)

    def timing(target, rate):
        if not rate:
            return None, None
        months = ceil(target / rate)
        weeks = ceil(Decimal(months) * budget['covered_days'] / (3 * 7))
        return months, weeks

    for goal in sorted(goals, key=lambda g: PRIORITIES[g.priority]):
        cumulative += money(goal.amount_eur)
        months, weeks = timing(cumulative, pool)
        fast_months, fast_weeks = timing(cumulative, capacity)
        result['goals'].append({'goal_id': goal.id, 'name': goal.name, 'priority': goal.priority,
                                'priority_label': PRIORITY_LABELS[goal.priority], 'target_eur': float(goal.amount_eur),
                                'monthly_allocation_eur': allocation[goal.id], 'completion_months': months,
                                'completion_weeks': weeks, 'save_all_extra_months': fast_months,
                                'save_all_extra_weeks': fast_weeks})
    return result


def preview_goal(customer, goals, proposed, as_of=None):
    before = goal_plan(customer, goals, as_of)
    after = goal_plan(customer, [*goals, proposed], as_of)
    changes = {}
    for key in ['daily_eur', 'weekly_eur', 'monthly_extra_eur']:
        changes[key] = (None if before[key] is None or after[key] is None
                        else float(money(after[key]) - money(before[key])))
    return {'before': before, 'after': after, 'spending_change': changes,
            'proposed_goal_id': proposed.id, 'saved': False,
            'note': 'Read-only preview. Negative change means less extra spending; zero can mean existing goal savings are reassigned.'}
