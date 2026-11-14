"""API integration tests with the two local demo customers; never print raw records."""

import unittest
from decimal import Decimal

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_two_customers_and_mortgages(self):
        customers = self.client.get('/api/customers').json()
        self.assertEqual([row['customer_id'] for row in customers], ['CUST04457', 'CUST00001'])
        for customer in customers:
            response = self.client.get(f"/api/customers/{customer['customer_id']}/mortgages")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(bool(response.json()['applications']), customer['has_mortgage_data'])
            for application in response.json()['applications']:
                self.assertIsNone(application['monthly_payment_eur'])

    def test_spending_excludes_transfers(self):
        for customer_id, customer in app.state.customers.items():
            response = self.client.get(f'/api/customers/{customer_id}/spending')
            self.assertEqual(response.status_code, 200)
            summary = response.json()
            rows = customer.get_transactions(summary['month'])
            expected = rows.loc[
                rows['transaction_type'].isin(['purchase', 'utilities_payment', 'housing_payment'])
                & (rows['tx_amount_eur'] < 0), 'tx_amount_eur'
            ].sum()
            self.assertAlmostEqual(summary['spending_eur'], round(-float(expected), 2))
            self.assertAlmostEqual(sum(point['amount_eur'] for point in summary['daily']), summary['spending_eur'])
            self.assertEqual(len(summary['daily']), __import__('calendar').monthrange(
                int(summary['month'][:4]), int(summary['month'][5:])
            )[1])

    def test_data_coach_for_both_original_profiles(self):
        for customer_id, customer in app.state.customers.items():
            base = f'/api/customers/{customer_id}'
            before = {name: self.client.get(f'{base}/{name}').json() for name in ['goals', 'assumptions', 'budget']}
            response = self.client.get(f'{base}/recorded-balances')
            self.assertEqual(response.status_code, 200)
            balances = response.json()
            self.assertFalse(balances['current_balance_known'])
            self.assertEqual(len(balances['accounts']), len(customer.get_account_ids()))
            latest = customer.get_account_balances()
            for account in balances['accounts']:
                expected = latest.loc[account['account_id'], 'balance_after_eur']
                if pd.isna(expected):
                    self.assertIsNone(account['balance_eur'])
                else:
                    self.assertEqual(account['balance_eur'], round(float(expected), 2))
            for period in ['week', 'month']:
                response = self.client.get(f'{base}/spending-comparison?period={period}')
                self.assertEqual(response.status_code, 200)
                comparison = response.json()
                self.assertFalse(comparison['coverage']['completeness_guaranteed'])
                if comparison['baseline']:
                    self.assertLess(comparison['baseline']['end'], comparison['comparison']['start'])
                    self.assertAlmostEqual(comparison['difference_eur'], comparison['comparison']['spending_eur']
                                           - comparison['baseline']['average_spending_eur'], places=2)
            response = self.client.get(f'{base}/planning-suggestions')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(all(not item['confirmed'] for item in response.json()['observations'].values()))
            periods = self.client.get(f'{base}/spending-history').json()['periods']
            eligible = [item for item in periods if not item['partial'] and item['categories']]
            if eligible:
                period = eligible[-1]
                category = next((key for key in period['categories'] if key.casefold() not in {'unknown', 'uncategorized'}), None)
                if category:
                    result = self.client.post(f'{base}/category-reduction', json={
                        'category': category, 'period': 'month', 'period_start': period['start'], 'reduction_percent': '20',
                    })
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.json()['baseline_spending_eur'], period['categories'][category])
                    self.assertIsNone(result.json()['goal_impact'])
            for name, value in before.items():
                self.assertEqual(self.client.get(f'{base}/{name}').json(), value)

    def test_budget_and_goal_priority(self):
        base = '/api/customers/CUST04457'
        budget = self.client.get(f'{base}/budget').json()
        self.assertIsNone(budget['daily_eur'])
        self.assertIsNone(budget['weekly_eur'])
        flexible = self.client.post(f'{base}/goals', json={
            'name': 'Trip', 'amount_eur': '100.10', 'priority': 'flexible'
        })
        critical = self.client.post(f'{base}/goals', json={
            'name': 'Emergency reserve', 'amount_eur': '200.20', 'priority': 'critical'
        })
        self.assertEqual(flexible.status_code, 201)
        self.assertEqual(critical.status_code, 201)
        before = self.client.get(f'{base}/goals').json()
        analysis = self.client.get(f'{base}/goal-analysis').json()
        self.assertEqual(analysis['ordered_goal_ids'], [critical.json()['id'], flexible.json()['id']])
        self.assertEqual(Decimal(analysis['total_target_eur']), Decimal('300.30'))
        self.assertEqual(self.client.get(f'{base}/goals').json(), before)
        self.assertEqual(self.client.get('/api/customers/CUST00001/goals').json(), [])

    def test_invalid_requests(self):
        self.assertEqual(self.client.get('/api/customers/unknown/budget').status_code, 404)
        base = '/api/customers/CUST04457'
        self.assertEqual(self.client.get(f'{base}/spending?month=2026-13').status_code, 422)
        self.assertEqual(self.client.get(f'{base}/spending?month=1900-01').status_code, 404)
        for payload in [
            {'name': ' ', 'amount_eur': 1, 'priority': 'critical'},
            {'name': 'Goal', 'amount_eur': -1, 'priority': 'critical'},
            {'name': 'Goal', 'amount_eur': '1.001', 'priority': 'critical'},
            {'name': 'Goal', 'amount_eur': 1, 'priority': 'other'},
        ]:
            self.assertEqual(self.client.post(f'{base}/goals', json=payload).status_code, 422)


if __name__ == '__main__':
    unittest.main()
