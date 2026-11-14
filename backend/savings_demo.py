"""Local, bounded what-if ranking; never a recommendation to cut essential spending."""

import re
from decimal import Decimal

from .data_coach import complete_windows, in_window, period_dates, total_amount
from .financial import money, spending_rows

CANDIDATES = ('restaurants', 'entertainment', 'travel')
SAVINGS_QUESTION = re.compile(
    r'where (?:could|can) i save (?:the )?most(?: in (\d{4}-\d{2}))?'
)


def savings_answer(normalized, customer):
    match = SAVINGS_QUESTION.fullmatch(normalized)
    if not match:
        return None
    windows = complete_windows(customer, 'month')
    requested = match.group(1)
    if requested:
        windows = [window for window in windows if str(window) == requested]
    if not windows:
        return 'No full recorded month matches this request. Choose a recorded month; missing records do not establish zero spending.'
    window = windows[-1]
    dates = period_dates(window)
    rows = in_window(spending_rows(customer), window)
    # Explicit bill types are protected even if their category has a misleading label.
    rows = rows[rows.transaction_type == 'purchase']
    labels = rows.category.fillna('').str.strip().str.casefold()
    ranking = []
    for category in CANDIDATES:
        selected = rows[labels == category]
        if selected.empty:
            continue
        baseline = total_amount(selected)
        reduction = money(baseline * Decimal('0.10'))
        ranking.append((category, baseline, reduction))
    ranking.sort(key=lambda item: (-item[2], item[0]))
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
