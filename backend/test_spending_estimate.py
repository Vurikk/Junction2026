"""Cash-only estimates: synthetic regressions and optional real demo customer checks."""
from copy import deepcopy
from datetime import date
import os
from types import SimpleNamespace
from unittest import TestCase, main, skipUnless
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.data_test import load_customers
from backend.main import app, Assumptions, SpendingEstimateInput
from backend.spending_estimate import estimate
from backend.test_data_coach import fixture


class EstimateTests(TestCase):
    def calculate(self, customer=None, **values):
        return estimate(customer or fixture(), SpendingEstimateInput(**values).model_dump(), [], {}, date(2026, 11, 14))

    def test_current_missing_three_and_no_history_promotion(self):
        result = self.calculate()
        self.assertEqual(result['missing_inputs'], [
            'available_funds_eur', 'emergency_reserve_eur', 'upcoming_essential_bills_eur'])
        self.assertIsNone(result['daily_eur'])
        self.assertIsNone(result['inputs']['available_funds_eur']['value_eur'])
        self.assertGreater(result['observations']['income']['recorded_income_eur'], 0)
        self.assertEqual(result['inputs']['voluntary_goal_contribution_eur']['source'], 'policy')

    def test_rent_due_tomorrow_is_not_prorated(self):
        result = self.calculate(available_funds_eur=1000, emergency_reserve_eur=100, upcoming_essential_bills_eur=700)
        self.assertEqual(result['status'], 'estimated')
        self.assertEqual(result['daily_eur'], 28.57)
        self.assertEqual(result['weekly_eur'], 199.99)
        self.assertIn('No money set aside', result['goal_policy'])
        self.assertEqual(result['inputs']['upcoming_essential_bills_eur']['value_eur'], 700)

    def test_historical_empty_history_is_unknown(self):
        customer = fixture()
        customer._transactions = customer._transactions.iloc[0:0].copy()
        result = self.calculate(customer, mode='historical')
        self.assertEqual(result['status'], 'insufficient_data')
        self.assertIsNone(result['reference_date'])
        self.assertIsNone(result['daily_eur'])
        self.assertIn('available_funds_eur', result['missing_inputs'])
        self.assertIsNone(result['observations']['bills']['value_eur'])

    def test_zero_and_shortfall(self):
        result = self.calculate(available_funds_eur=0, emergency_reserve_eur=0, upcoming_essential_bills_eur=0)
        self.assertEqual(result['daily_eur'], 0)
        self.assertFalse(result['missing_inputs'])
        self.assertEqual(self.calculate(available_funds_eur=100, emergency_reserve_eur=50,
                                        upcoming_essential_bills_eur=200)['shortfall_eur'], 150)

    def test_bill_history_and_actual_calendar_day_scaling(self):
        customer = fixture(records=[
            ('2024-01-01', 'housing_payment', -620, 'housing', 'one', 2000),
            ('2024-01-02', 'purchase', -310, 'food', 'one', 1690),
            ('2024-01-03', 'transfer', -99999, 'food', 'one', 1690),
            ('2024-01-31', 'transfer', 0, 'transfer', 'one', 1690),
        ])
        result = self.calculate(customer, additional_essential_bills_eur=0)
        self.assertIn('upcoming_essential_bills_eur', result['missing_inputs'])
        self.assertEqual(result['observations']['bills']['value_eur'], 140)
        self.assertEqual(result['observations']['everyday_purchases']['value_eur'], 70)
        historical = self.calculate(customer, mode='historical', emergency_reserve_eur=100, additional_essential_bills_eur=0)
        self.assertEqual(historical['reference_date'], '2024-01-31')
        self.assertEqual(historical['status'], 'estimated')
        self.assertEqual(historical['daily_eur'], 207.14)
        self.assertFalse(historical['observations']['balances']['current_balance_known'])

    def test_async_missing_future_balances_are_not_summed(self):
        customer = fixture(records=[('2024-01-01', 'purchase', -1, 'food', 'one', 100),
                                    ('2024-01-02', 'purchase', -1, 'food', 'two', 200)])
        result = self.calculate(customer, mode='historical', emergency_reserve_eur=0, upcoming_essential_bills_eur=0)
        self.assertIn('available_funds_eur', result['missing_inputs'])
        customer._transactions.loc[1, 'tx_timestamp'] = customer._transactions.loc[0, 'tx_timestamp']
        result = self.calculate(customer, mode='historical', emergency_reserve_eur=0, upcoming_essential_bills_eur=0)
        self.assertEqual(result['reference_date'], '2024-01-01')
        customer._transactions.loc[1, 'balance_after_eur'] = float('nan')
        self.assertIn('available_funds_eur', self.calculate(customer, mode='historical')['missing_inputs'])

    def test_goals_protect_costs_priority_and_no_repeat(self):
        customer = fixture()
        goals = [SimpleNamespace(id=p, priority=p, amount_eur=200) for p in ['flexible', 'important', 'critical']]
        payload = SpendingEstimateInput(available_funds_eur=1000, emergency_reserve_eur=200,
                                       upcoming_essential_bills_eur=400, everyday_spending_eur=100,
                                       voluntary_goal_contribution_eur=300).model_dump()
        before = deepcopy(payload)
        result = estimate(customer, payload, goals, {})
        self.assertEqual([g['allocated_eur'] for g in result['allocations']], [200, 100, 0])
        self.assertTrue(all(g['completion_periods'] is None for g in result['allocations']))
        self.assertEqual(result['daily_eur'], 14.28)
        self.assertEqual(payload, before)
        payload['upcoming_essential_bills_eur'] = 1000
        self.assertEqual(estimate(customer, payload, goals, {})['savings_capacity_eur'], 0)


class EstimateApiTests(TestCase):
    def test_profiles_validation_and_manual_plan_nonmutation(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), patch('backend.main.load_customers',
                return_value=[fixture(), fixture('CUST00001')]), TestClient(app) as client:
            for customer_id in ['CUST04457', 'CUST00001']:
                base = f'/api/customers/{customer_id}'
                payload = {field: '0.00' for field in client.get(base + '/budget').json()['missing_inputs']}
                client.put(base + '/assumptions', json=payload)
                client.post(base + '/goals', json={'name': 'Reserve', 'amount_eur': '100', 'priority': 'critical'})
                before = {k: client.get(base + '/' + k).json() for k in ['goals', 'assumptions', 'budget']}
                self.assertTrue(client.get(base + '/spending-estimate').json()['manual_plan_available'])
                result = client.post(base + '/spending-estimate', json={
                    'available_funds_eur': '1000', 'emergency_reserve_eur': '100', 'upcoming_essential_bills_eur': '700'})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()['weekly_eur'], 199.99)
                for k, value in before.items():
                    self.assertEqual(client.get(base + '/' + k).json(), value)
                for changes in [{'horizon_days': 0}, {'available_funds_eur': -1}, {'emergency_reserve_eur': 'NaN'},
                                {'mode': 'today'}, {'confirmed_income_eur': 100}, {'available_funds_eur': '1.001'}]:
                    self.assertEqual(client.post(base + '/spending-estimate', json=changes).status_code, 422)
            self.assertEqual(client.get('/api/customers/unknown/spending-estimate').status_code, 404)


@skipUnless(os.environ.get('SBANK_DATA_DIR'), 'Set SBANK_DATA_DIR for local demo dataset regression')
class RealDemoEstimateTests(TestCase):
    def test_both_customers_cash_only_and_read_only(self):
        for customer in load_customers(os.environ['SBANK_DATA_DIR']):
            before = customer.get_transactions()
            default = estimate(customer, SpendingEstimateInput().model_dump(), [], {})
            self.assertIsNone(default['daily_eur'])
            result = estimate(customer, SpendingEstimateInput(available_funds_eur=1000, emergency_reserve_eur=100,
                              upcoming_essential_bills_eur=700).model_dump(), [], {})
            self.assertEqual(result['weekly_eur'], 199.99)
            self.assertTrue(customer.get_transactions().equals(before))


if __name__ == '__main__':
    main()
