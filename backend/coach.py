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


def answer(question, analysis, goals, recorded=None, preview=None, mortgage_available=None):
    words = set(re.findall(r"[a-z]+", question.lower()))
    normalized = ' '.join(re.findall(r"[a-z]+", question.lower()))
    categories = {name for period in (recorded or {}).get('periods', []) for name in period['categories']}
    matched_categories = {
        name for name in categories
        if ' ' + ' '.join(re.findall(r"[a-z]+", name.lower())) + ' ' in ' ' + normalized + ' '
    }
    result = {'kind': 'help', 'text': 'Ask about categories, averages, allowances, goals, or a what-if goal.', 'rows': []}
    if preview is not None:
        result.update(kind='scenario', text='Preview only. ' + goal_message(analysis, goals), preview=preview)
    elif words & {'what', 'scenario', 'preview'} and words & {'if', 'scenario', 'preview'}:
        result.update(kind='scenario', text='Enter a goal name, amount and priority below to preview it. Nothing is saved.')
    elif words & {'mortgage', 'mortgages'}:
        text = ('Linked mortgage application data is available. ' if mortgage_available else
                'No linked mortgage application data is available. ')
        text += 'Applications do not establish active debt. Monthly repayments are unknown; confirm actual bills on Home.'
        result.update(kind='mortgage', text=text)
    elif words & {'balance', 'balances'}:
        result.update(kind='unknown', text='Current account balances are unknown. Historical balances are not current accessible funds.')
    elif words & {'goal', 'goals', 'progress', 'saved'}:
        result.update(kind='goals', text=goal_message(analysis, goals))
    elif words & {'allowance', 'daily', 'weekly', 'afford', 'spendable'} and not words & {'average', 'historical'}:
        if analysis['missing_inputs']:
            text = 'Confirm on Home: ' + ', '.join(LABELS[k] for k in analysis['missing_inputs']) + '.'
        else:
            text = f"Estimated room: {euro(analysis['daily_eur'])}/day; {euro(analysis['weekly_eur'])}/week. Includes everyday costs."
            if analysis['shortfall_eur']:
                text += f" Bills and reserve are short by {euro(analysis['shortfall_eur'])}."
        result.update(kind='allowance', text=text)
    elif words & {'spending', 'category', 'categories', 'average', 'historical'} or matched_categories:
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
            if matched_categories:
                rows = [r for r in rows if r['label'] in matched_categories]
            result.update(kind='categories', text=f"Recorded categories for {latest['period']}"
                          + (' (partial month).' if latest['partial'] else '.') + ' Transfers and refunds excluded.',
                          rows=rows)
            if matched_categories and not rows:
                result['text'] += ' No included payments for the requested category in this month; this does not prove complete coverage.'
    return result
