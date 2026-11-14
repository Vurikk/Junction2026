"""Synthetic tests: no customer files required."""
import unittest
from types import SimpleNamespace

import pandas as pd

from backend.financial import history, income, plan



class FinancialTests(unittest.TestCase):
    def assumptions(self, **changes):
        values = dict(available_funds_eur=1000, confirmed_income_eur=0, upcoming_essential_bills_eur=400,
                      emergency_reserve_eur=200, everyday_spending_eur=100, voluntary_goal_contribution_eur=300,
                      horizon_days=30, repeat_plan=True)
        values.update(changes)
        return values

    def test_missing_and_explicit_zero(self):
        self.assertIsNone(plan({}, [])['daily_eur'])
        result = plan(self.assumptions(available_funds_eur=0), [])
        self.assertEqual(result['daily_eur'], 0)
        self.assertEqual(result['shortfall_eur'], 600)

    def test_priority_and_protection(self):
        goals = [SimpleNamespace(id=p, priority=p, amount_eur=200) for p in ['flexible', 'important', 'critical']]
        result = plan(self.assumptions(), goals)
        self.assertEqual([g['allocated_eur'] for g in result['allocations']], [200, 100, 0])
        self.assertEqual([g['completion_periods'] for g in result['allocations']], [1, 2, 2])
        self.assertEqual(result['daily_eur'], 3.33)
        self.assertEqual(plan(self.assumptions(upcoming_essential_bills_eur=1000), goals)['savings_capacity_eur'], 0)
        self.assertIsNone(plan(self.assumptions(repeat_plan=False), goals)['allocations'][0]['completion_periods'])

    def customer(self):
        rows = pd.DataFrame([
            ('2024-01-01', 'transfer', -999, 'transfer'),
            ('2024-01-01', 'salary', 2000, 'income'),
            ('2024-02-01', 'salary', 2000, 'income'),
            ('2024-03-01', 'salary', 2000, 'income'),
            ('2024-03-31', 'purchase', -30, 'unknown'),
            ('2024-01-20', 'housing_payment', -100, 'housing'),
            ('2024-01-21', 'refund', 20, 'housing'),
        ], columns=['tx_date', 'transaction_type', 'tx_amount_eur', 'category'])
        rows.tx_date = pd.to_datetime(rows.tx_date)
        return SimpleNamespace(customer_id='demo', get_transactions=lambda: rows.copy())

    def test_history_and_income(self):
        customer = self.customer()
        monthly = history(customer, 'month', 80)
        self.assertEqual([p['spending_eur'] for p in monthly['periods']], [100, 0, 30])
        self.assertEqual(monthly['historical_average_eur'], 43.33)
        self.assertEqual(monthly['periods'][0]['remaining_budget_eur'], -20)
        self.assertEqual(monthly['periods'][2]['baskets']['uncertain'], 30)
        weekly = history(customer, 'week')
        self.assertEqual(sum(p['spending_eur'] for p in weekly['periods']), 130)
        analyzed = income(customer)
        self.assertEqual(analyzed['recorded_income_eur'], 6000)
        self.assertEqual(len(analyzed['likely_recurring']), 1)
        self.assertFalse(analyzed['likely_recurring'][0]['confirmed'])


if __name__ == '__main__':
    unittest.main()
