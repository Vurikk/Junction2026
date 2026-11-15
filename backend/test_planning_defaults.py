import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.planning_defaults import planning_defaults, income_remainder, spending_plan_target
from backend.test_data_coach import fixture


def sample():
    return fixture(records=[
        ('2024-04-01', 'salary', 3000, 'income', 'one', 3000),
        ('2024-04-10', 'housing_payment', -900, 'groceries', 'one', 2100),
        ('2024-04-11', 'utilities_payment', -100, 'utilities', 'one', 2000),
        ('2024-04-12', 'purchase', -300, 'Groceries', 'one', 1700),
        ('2024-04-13', 'purchase', -100, 'Restaurants', 'one', 1600),
        ('2024-04-14', 'transfer', -9999, 'groceries', 'one', 1600),
        ('2024-04-15', 'refund', 50, 'groceries', 'one', 1650),
        ('2024-04-30', 'transfer', 0, 'transfer', 'one', 1650),
    ])


class PlanningDefaultsTests(unittest.TestCase):
    def test_spending_target_uses_saved_costs_not_reserve_or_goal_transfers(self):
        values = dict(horizon_days=60, upcoming_essential_bills_eur=2000, everyday_spending_eur=400,
                      emergency_reserve_eur=9000, voluntary_goal_contribution_eur=500)
        self.assertEqual(spending_plan_target(values, 'month'), 1200)
        self.assertEqual(spending_plan_target(values, 'week'), 280)
        self.assertIsNone(spending_plan_target({}, 'month'))
        self.assertEqual(spending_plan_target({**values, 'monthly_budget_eur': 0}, 'month'), 0)

    def test_income_remainder_missing_zero_and_excess_goals(self):
        self.assertIsNone(income_remainder()['remaining_income_eur'])
        before = income_remainder(3000, 1400, 400)
        self.assertEqual(before['remaining_income_eur'], 1200)
        self.assertFalse(before['goal_contribution_included'])
        self.assertEqual(income_remainder(3000, 1400, 400, 200)['remaining_income_eur'], 1000)
        self.assertEqual(income_remainder(3000, 1400, 400, 1500)['remaining_income_eur'], -300)
        self.assertTrue(income_remainder(0, 0, 0, 0)['goal_contribution_included'])

    def test_amounts_horizon_scaling_and_no_food_double_count(self):
        for horizon, salary, bills in [(30, 3000, 1300), (15, 1500, 650), (60, 6000, 2600)]:
            result = planning_defaults(sample(), horizon)
            self.assertEqual(result['balance']['amount_eur'], 1650)
            self.assertEqual(result['income']['amount_eur'], salary)
            self.assertEqual(result['bills']['total_eur'], bills)
            self.assertEqual(len(result['bills']['items']), 3)

    def test_reserve_and_remaining_spending_are_independent_of_bills_and_horizon(self):
        result = planning_defaults(sample(), 30)
        self.assertEqual(result['everyday']['amount_eur'], 100)
        self.assertEqual(result['everyday']['daily_average_eur'], 3.33)
        self.assertEqual(result['reserve']['monthly_expenses_eur'], 1400)
        self.assertEqual(result['reserve']['options'][2], {'months': 3, 'amount_eur': 4200, 'exceeds_balance': True})
        self.assertEqual(result['reserve']['options'][0]['exceeds_balance'], False)
        self.assertEqual(result['reserve']['options'][11]['amount_eur'], 16800)
        longer = planning_defaults(sample(), 60)
        self.assertEqual(longer['everyday']['amount_eur'], 200)
        self.assertEqual(longer['reserve'], result['reserve'])
        self.assertEqual(result['bills']['total_eur'] + result['everyday']['amount_eur'], 1400)

    def test_missing_values_and_mixed_account_dates_stay_unknown(self):
        customer = sample()
        customer._transactions.loc[customer._transactions.transaction_type == 'utilities_payment', 'transaction_type'] = 'unknown'
        result = planning_defaults(customer)
        self.assertIsNone(result['bills']['total_eur'])
        self.assertIsNone(result['bills']['items'][1]['amount_eur'])
        customer._transactions.loc[0, 'bank_account_id'] = 'other'
        self.assertIsNone(planning_defaults(customer)['balance']['amount_eur'])
        customer._transactions.loc[customer._transactions.transaction_type == 'salary', 'transaction_type'] = 'transfer'
        self.assertIsNone(planning_defaults(customer)['income']['amount_eur'])

    def test_negative_and_missing_latest_balance_not_replaced(self):
        for value in [None, -10]:
            customer = sample()
            customer._transactions.loc[customer._transactions.index[-1], 'balance_after_eur'] = value
            self.assertIsNone(planning_defaults(customer)['balance']['amount_eur'])

    def test_read_only_http_validation_and_no_silent_confirmation(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), patch('backend.main.load_customers', return_value=[sample()]):
            with TestClient(app) as client:
                base = '/api/customers/CUST04457/'
                before = {key: client.get(base + key).json() for key in ['assumptions', 'goals', 'budget']}
                remainder = client.post(base + 'planning-remainder', json={
                    'confirmed_income_eur': '3000', 'upcoming_essential_bills_eur': '1400',
                    'everyday_spending_eur': '400', 'voluntary_goal_contribution_eur': '200'})
                self.assertEqual(remainder.json()['remaining_income_eur'], 1000)
                self.assertEqual(client.post(base + 'planning-remainder', json={'confirmed_income_eur': '-1'}).status_code, 422)
                result = client.get(base + 'planning-defaults').json()
                self.assertEqual(result['balance']['amount_eur'], 1650)
                for horizon in ['0', '367', '1.5']:
                    self.assertEqual(client.get(base + 'planning-defaults?horizon_days=' + horizon).status_code, 422)
                self.assertEqual(client.get('/api/customers/missing/planning-defaults').status_code, 404)
                self.assertEqual(before, {key: client.get(base + key).json() for key in before})


if __name__ == '__main__':
    unittest.main()
