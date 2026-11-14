"""Curated chat answers: deterministic Python only, no provider or financial writes."""
from math import ceil
from decimal import Decimal

from .automatic_demo_budget import automatic_budget
from .data_coach import complete_windows, in_window, period_dates, spending_comparison, total_amount
from .financial import money, spending_rows
from .savings_demo import savings_opportunities


def answer(customer, goals, action, percent=10, month=None, category=None):
    result = {'mode': 'guided', 'text': '', 'rows': [], 'source_period': None, 'actions': [],
              'note': 'Guided demo. Calculations use recorded data, not an LLM. Nothing is changed.'}
    if action == 'tips':
        result['text'] = 'Try one small change you can keep.'
        result['tips'] = ['Plan a few meals and check what you already have before shopping.',
                          'Pause before nonessential online purchases; revisit your wish list the next day.',
                          'Review restaurants, entertainment or travel only where a cut is realistic. Protect necessities.']
        return result
    if action in {'goals', 'allowance'}:
        budget = automatic_budget(customer, goals)
        result['source_period'] = budget['source_period']
        if not goals:
            result['text'] = 'Create a goal first: give it a name, amount and priority. Then I can explain the plan here.'
            result['note'] = 'Use Add goal on Home or the Goals tab. This chat does not save or change goals.'
            return result
        if budget['status'] != 'estimated':
            result['text'] = 'There is not enough reliable recorded data to estimate this plan yet.'
            result['tips'] = [f"{g.name}: {g.priority} priority. Timing is unknown." for g in goals]
            return result
        result['note'] = ('Historical scenario, not current cash or guaranteed savings. App assumptions: protect usual spending; '
                          'reserve up to 10% of income, then allocate 50% of the remaining surplus to goals. '
                          'Actual saved progress is unknown. No goals are changed.')
        if action == 'allowance':
            result['text'] = 'Here is the extra room above your usual spending after the demo reserve and goal allocations.'
            result['rows'] = [{'label': 'Extra per day', 'value': budget['daily_eur']},
                              {'label': 'Extra per week', 'value': budget['weekly_eur']},
                              {'label': 'Planned goal savings per typical month', 'value': budget['goal_allocated_eur']}]
            return result
        result['text'] = 'Critical goals come first, followed by important and flexible goals.'
        if budget['goal_allocated_eur'] == 0:
            result['text'] += ' This recorded pattern leaves no room for goal savings after protected costs and the reserve policy.'
        lookup = {g.id: g for g in goals}
        for item in budget['goal_allocations']:
            goal = lookup[item['goal_id']]
            allocated = money(item['allocated_eur'])
            months = ceil(money(goal.amount_eur) / allocated) if allocated else None
            unit = 'month' if months == 1 else 'months'
            detail = (f'About {months} {unit} only if this monthly allocation continues; starting from no known saved amount.'
                      if months else 'No allocation in this scenario; completion time is unknown.')
            result['rows'].append({'label': f'{goal.name} · {goal.priority}', 'value': float(allocated),
                                   'detail': f'EUR {money(goal.amount_eur):.2f} target. {detail}'})
        result['text'] += ' Amounts below are planned savings per typical month, not money already saved.'
        result['actions'] = [{'label': 'Where could I save more?', 'action': 'savings'}]
        return result
    if action == 'comparison':
        comparison = spending_comparison(customer, 'month')
        result['source_period'] = comparison['comparison']
        if comparison['status'] == 'insufficient_data':
            result['text'] = 'I need at least two complete recorded months to compare your spending.'
            return result
        difference = money(comparison['difference_eur'])
        result['text'] = (f'You spent EUR {abs(difference):.2f} '
                          f'{"more" if difference > 0 else "less" if difference < 0 else "different"} '
                          'than the average of earlier recorded months.')
        if difference == 0:
            result['text'] = 'Your spending matched the average of earlier recorded months.'
        result['rows'] = [{'label': 'Latest full recorded month', 'value': comparison['comparison']['spending_eur']},
                          {'label': 'Earlier monthly average', 'value': comparison['baseline']['average_spending_eur']}]
        baseline = comparison['baseline']
        result['note'] = f"Earlier average: {baseline['start']} to {baseline['end']}. Recorded coverage may be incomplete."
        return result
    if action == 'savings':
        data = savings_opportunities(customer, month, percent)
        result['source_period'] = data['source_period']
        result['note'] = ('Hypothetical cuts, not actual savings. Only restaurants, entertainment and travel are compared. '
                          'These costs may still be necessary; protect essential bills and reserves.')
        candidates = data['candidates']
        if category:
            candidates = [c for c in candidates if c['category'] == category]
        if not candidates:
            result['text'] = 'No matching purchases are recorded in this month. I cannot infer zero spending or savings.'
            return result
        top = candidates[0]
        result['text'] = (f"Among the categories reviewed, {top['category']} has the largest potential reduction at {percent}%. "
                          'Choose a cut only if it works for you.')
        if category:
            result['text'] = f"Here is what spending {percent}% less on {category} would have looked like."
        for item in candidates:
            result['rows'].append({'label': item['category'].capitalize(), 'value': item['potential_reduction_eur'],
                                   'detail': f"EUR {item['baseline_spending_eur']:.2f} recorded → "
                                             f"EUR {item['hypothetical_spending_eur']:.2f} after the hypothetical cut."})
        selected_month = data['source_period']['start'][:7]
        result['actions'] = [{'label': f'Try {p}% less on {top["category"]}', 'action': 'savings',
                              'percent': p, 'month': selected_month, 'category': top['category']} for p in (10, 20) if p != percent]
        result['actions'].append({'label': 'Analyze my goals', 'action': 'goals'})
        return result
    windows = complete_windows(customer, 'month')
    if not windows:
        result['text'] = 'There is no full recorded month to summarize yet.'
        return result
    window = windows[-1]
    rows = in_window(spending_rows(customer), window)
    result['source_period'] = period_dates(window)
    totals = [(str(label), total_amount(group)) for label, group in rows.groupby(rows.category.fillna('Uncategorized'))]
    totals.sort(key=lambda item: (-item[1], item[0]))
    result['text'] = f'Your recorded spending was EUR {total_amount(rows):.2f}. Here are the largest categories.'
    result['rows'] = [{'label': label, 'value': float(value)} for label, value in totals[:5]]
    if len(totals) > 5:
        result['rows'].append({'label': 'Other categories', 'value': float(sum((v for _, v in totals[5:]), Decimal(0)))})
    result['note'] = 'Gross recorded purchases, housing and utilities. Transfers and refunds excluded; coverage may be incomplete.'
    result['actions'] = [{'label': 'What could I save most on?', 'action': 'savings'},
                         {'label': 'Compare with usual', 'action': 'comparison'}]
    return result
