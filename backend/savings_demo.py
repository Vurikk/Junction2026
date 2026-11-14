"""Local, bounded what-if ranking; never a recommendation to cut essential spending."""

import re
from decimal import Decimal

from .data_coach import complete_windows, in_window, period_dates, total_amount
from .financial import money, spending_rows

CANDIDATES = ('restaurants', 'entertainment', 'travel')
SAVINGS_QUESTION = re.compile(
    r'where (?:could|can) i save (?:the )?most(?: in (\d{4}-\d{2}))?'
)


def savings_opportunities(customer, month=None, reduction_percent=10):
    """Aggregate only an explicit month or the latest full recorded month; no financial state writes."""
    percent = Decimal(str(reduction_percent))
    if not percent.is_finite() or not 0 <= percent <= 100:
        raise ValueError('Use a reduction between 0 and 100 percent.')
    windows = complete_windows(customer, 'month')
    if month is not None:
        windows = [window for window in windows if str(window) == month]
    result = {
        'currency': 'EUR', 'status': 'unavailable_period', 'source_period': None,
        'reduction_percent': float(percent), 'candidates': [],
        'note': ('Review candidates only: restaurant, entertainment and travel purchases may still be necessary. '
                 'Protect essential bills and emergency reserves. Other categories, bill payments, transfers and refunds '
                 'are excluded. Recorded coverage may be incomplete. Hypothetical reductions are not actual savings; '
                 'goals, allowances and confirmed inputs are unchanged.'),
    }
    if not windows:
        return result
    window = windows[-1]
    result['source_period'] = period_dates(window)
    rows = in_window(spending_rows(customer), window)
    # Explicit bill types are protected even if their category has a misleading label.
    rows = rows[rows.transaction_type == 'purchase']
    labels = rows.category.fillna('').str.strip().str.casefold()
    for category in CANDIDATES:
        selected = rows[labels == category]
        if selected.empty:
            continue
        baseline = total_amount(selected)
        reduction = money(baseline * percent / 100)
        result['candidates'].append({
            'category': category, 'baseline_spending_eur': float(baseline),
            'hypothetical_spending_eur': float(baseline - reduction), 'potential_reduction_eur': float(reduction),
        })
    result['candidates'].sort(key=lambda item: (-Decimal(str(item['potential_reduction_eur'])), item['category']))
    result['status'] = 'available' if result['candidates'] else 'no_candidates'
    return result


def savings_answer(normalized, customer):
    match = SAVINGS_QUESTION.fullmatch(normalized)
    if not match:
        return None
    result = savings_opportunities(customer, match.group(1))
    if result['status'] == 'unavailable_period':
        return 'No full recorded month matches this request. Choose a recorded month; missing records do not establish zero spending.'
    dates = result['source_period']
    ranking = [(item['category'], Decimal(str(item['baseline_spending_eur'])), Decimal(str(item['potential_reduction_eur'])))
               for item in result['candidates']]
    prefix = (f"For {dates['start']} to {dates['end']}, comparing a hypothetical 10% cut "
              'in recorded restaurant, entertainment and travel purchases: ')
    if not ranking:
        return prefix + ('No matching purchases are recorded. This does not prove zero spending or no possible savings. '
                         'I have not substituted an older month. Recorded coverage may be incomplete.')
    details = '; '.join(
        f'{category}: EUR {baseline:.2f} recorded -> EUR {baseline - reduction:.2f}, '
        f'potential reduction EUR {reduction:.2f}' for category, baseline, reduction in ranking
    )
    leaders = [category for category, _, reduction in ranking if reduction == ranking[0][2]]
    headline = ('Largest potential reduction among these categories: ' + ', '.join(leaders) + '. '
                if ranking[0][2] > 0 else 'All potential reductions round to EUR 0.00. ')
    return (prefix + headline + details + '. These are review candidates, not confirmed nonessential costs; '
            'travel or meals may be necessary. Protect essential bills and emergency reserves. '
            'Other categories, bill payments, transfers and refunds are excluded. Coverage may be incomplete. '
            'Hypothetical reductions are not actual savings; goals, allowances and confirmed inputs are unchanged.')
