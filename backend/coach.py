"""Deterministic presentation layer; financial calculations remain in financial.py."""
import re
from decimal import Decimal

LABELS = {
    'available_funds_eur': 'accessible funds', 'confirmed_income_eur': 'confirmed income',
    'upcoming_essential_bills_eur': 'essential bills', 'emergency_reserve_eur': 'emergency reserve',
    'everyday_spending_eur': 'everyday costs', 'voluntary_goal_contribution_eur': 'goal contribution',
}


def euro(value):
    return f"EUR {Decimal(str(value)):,.2f}"


def goal_message(analysis, goals):
    if not goals:
        return 'Add a goal to see what your plan can fund.'
    if analysis['missing_inputs']:
        return 'To check your goals, confirm on Home: ' + ', '.join(LABELS[k] for k in analysis['missing_inputs']) + '.'
    names = {g.id: g.name for g in goals}
    parts = [f"{names[a['goal_id']]}: {euro(a['allocated_eur'])} planned" for a in analysis['allocations']]
    return '; '.join(parts) + '. These are planned amounts; saved progress is unknown.'


def answer(question, analysis, goals, recorded=None, preview=None):
    words = set(re.findall(r"[a-z]+", question.lower()))
    result = {'kind': 'help', 'text': 'Ask about categories, averages, allowances, goals, or a what-if goal.', 'rows': []}
    if preview is not None:
        result.update(kind='scenario', text='Preview only. ' + goal_message(analysis, goals), preview=preview)
    elif words & {'what', 'scenario', 'preview'} and words & {'if', 'scenario', 'preview'}:
        result.update(kind='scenario', text='Enter a goal name, amount and priority below to preview it. Nothing is saved.')
    elif words & {'goal', 'goals', 'progress', 'saved'}:
        result.update(kind='goals', text=goal_message(analysis, goals))
    elif words & {'allowance', 'daily', 'weekly', 'afford', 'spendable'}:
        if analysis['missing_inputs']:
            text = 'Confirm on Home: ' + ', '.join(LABELS[k] for k in analysis['missing_inputs']) + '.'
        else:
            text = f"Estimated room: {euro(analysis['daily_eur'])}/day; {euro(analysis['weekly_eur'])}/week. Includes everyday costs."
            if analysis['shortfall_eur']:
                text += f" Bills and reserve are short by {euro(analysis['shortfall_eur'])}."
        result.update(kind='allowance', text=text)
    elif words & {'spending', 'category', 'categories', 'average', 'historical'}:
        periods = (recorded or {}).get('periods', [])
        if not periods:
            result.update(kind='spending', text='No recorded spending history. Transaction dates, types and amounts are needed.')
        elif words & {'average', 'historical'}:
            complete = [p for p in periods if not p['partial']]
            avg = recorded['historical_average_eur']
            if not complete or avg is None:
                text = 'A full calendar month of transactions is needed for an average.'
            else:
                latest = complete[-1]
                delta = Decimal(str(latest['spending_eur'])) - Decimal(str(avg))
                text = f"{latest['period']}: {euro(latest['spending_eur'])}, {euro(abs(delta))} "
                text += ('above' if delta >= 0 else 'below') + f" the full-month average of {euro(avg)}. Coverage may be incomplete."
            result.update(kind='average', text=text)
        else:
            latest = periods[-1]
            rows = [{'label': k, 'value': v} for k, v in latest['categories'].items()]
            matched = [r for r in rows if r['label'].lower() in question.lower()]
            result.update(kind='categories', text=f"Recorded categories for {latest['period']}"
                          + (' (partial month).' if latest['partial'] else '.') + ' Transfers and refunds excluded.',
                          rows=matched or rows)
    return result
