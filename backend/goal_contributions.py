"""Explicit user-requested demo schedule; never booked transactions or saved progress."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd


def contribution_demo(goals, today=None):
    today = today or datetime.now(ZoneInfo('Europe/Helsinki')).date()
    current = pd.Period(today, freq='M')
    months = [current - offset for offset in range(6, 0, -1)]
    ordered = sorted(goals, key=lambda goal: {'critical': 0, 'important': 1, 'flexible': 2}[goal.priority])
    series = []
    chart = [{'month': str(month), 'values': {}} for month in months]
    for goal in ordered:
        demo = ' '.join(goal.name.casefold().split()) == 'new car'
        points = [{'month': str(month), 'planned_eur': 400.0, 'cumulative_planned_eur': float(400 * (index + 1))}
                  for index, month in enumerate(months)] if demo else []
        for row, point in zip(chart, points):
            row['values'][goal.id] = point['cumulative_planned_eur']
        series.append({'goal_id': goal.id, 'name': goal.name, 'priority': goal.priority,
                       'target_eur': float(goal.amount_eur), 'monthly_planned_eur': 400.0 if demo else None,
                       'total_planned_eur': float(400 * len(months)) if demo else None, 'months': points})
    return {'currency': 'EUR', 'kind': 'demo_planned', 'actual_saved_eur': None, 'chart_data': chart,
            'note': 'Demo: cumulative planned transfers to savings, not completed deposits or actual saved progress.',
            'goals': series}
