"""Explicit user-requested demo schedule; never booked transactions or saved progress."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd


def contribution_demo(goals, today=None):
    today = today or datetime.now(ZoneInfo('Europe/Helsinki')).date()
    current = pd.Period(today, freq='M')
    months = [current - offset for offset in range(6, 0, -1)]
    return {'currency': 'EUR', 'kind': 'demo_planned', 'actual_saved_eur': None,
            'note': 'Demo: planned transfers to a savings account, not completed deposits or actual saved progress.',
            'goals': [{'goal_id': goal.id, 'name': goal.name, 'monthly_planned_eur': 400.0, 'total_planned_eur': float(400 * len(months)),
                       'months': [{'month': str(month), 'planned_eur': 400.0} for month in months]}
                      for goal in goals if ' '.join(goal.name.casefold().split()) == 'new car']}
