"""Automatic historical demo policy, independently checked with synthetic and real profiles."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import os
from types import SimpleNamespace
from unittest import TestCase, main, skipUnless
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.automatic_demo_budget import automatic_budget
from backend.data_test import load_customers
from backend.main import app
from backend.test_data_coach import fixture


def goal(target=1000, priority='critical'):
    return SimpleNamespace(id=priority, priority=priority, amount_eur=target)


def customer(income=1000, spend=600, customer_id="CUST04457"):
    records = []
    for month in ['01', '02', '03']:
        records.extend([
            (f'2024-{month}-01', 'salary', income, 'income', 'one', 1000),
            (f'2024-{month}-10', 'purchase', -spend, 'Groceries', 'one', 400),
            (f'2024-{month}-11', 'transfer', -9999, 'unknown', 'one', 400),
            (f'2024-{month}-12', 'refund', 100, 'Groceries', 'one', 500),
        ])
    records.append(('2024-04-01', 'transfer', 0, 'unknown', 'one', 500))
    return fixture(customer_id=customer_id, records=records)


class AutomaticTests(TestCase):
    def test_oracle_same_months_and_actual_day_denominator(self):
        result = automatic_budget(customer(), [goal()], date(2026, 11, 14))
        self.assertEqual(result['source_period'], {'start': '2024-01-01', 'end': '2024-03-31'})
        self.assertEqual(result['covered_days'], 91)
        for key, expected in [('income_eur', 1000), ('protected_spending_eur', 600), ('reserve_contribution_eur', 100),
                              ('goal_budget_eur', 150), ('goal_allocated_eur', 150), ('monthly_extra_eur', 150),
                              ('daily_eur', 4.94), ('weekly_eur', 34.58)]:
            self.assertEqual(result[key], expected, key)
        self.assertIsNone(result['goal_allocations'][0]['completion_periods'])

    def test_target_cap_returns_unused_capacity_and_priority(self):
        result = automatic_budget(customer(), [goal(20)])
        self.assertEqual(result['monthly_extra_eur'], 280)
        self.assertEqual(result['goal_allocated_eur'], 20)
        result = automatic_budget(customer(), [goal(100, p) for p in ['flexible', 'important', 'critical']])
        self.assertEqual([g['allocated_eur'] for g in result['goal_allocations']], [100, 50, 0])

    def test_protection_deficit_and_reserve_shortfall(self):
        result = automatic_budget(customer(spend=1100), [goal()])
        self.assertEqual(result['deficit_eur'], 100)
        self.assertEqual(result['reserve_shortfall_eur'], 100)
        self.assertEqual(result['daily_eur'], 0)
        result = automatic_budget(customer(spend=950), [goal()])
        self.assertEqual(result['reserve_contribution_eur'], 50)
        self.assertEqual(result['reserve_shortfall_eur'], 50)
        self.assertEqual(result['goal_allocated_eur'], 0)

    def test_missing_evidence_and_no_goals(self):
        sample = customer()
        sample._transactions = sample._transactions[
            ~((sample._transactions.tx_date.dt.month == 2) & (sample._transactions.transaction_type == 'salary'))]
        result = automatic_budget(sample, [goal()])
        self.assertEqual(result['status'], 'insufficient_data')
        self.assertIn('income_evidence:2024-02', result['missing_inputs'])
        self.assertIsNone(result['income_eur'])
        result = automatic_budget(customer(), [])
        self.assertEqual(result['status'], 'needs_goal')
        self.assertEqual(result['action'], 'create_goal')
        self.assertIsNone(result['daily_eur'])
        sample._transactions = sample._transactions.iloc[0:0].copy()
        self.assertEqual(automatic_budget(sample, [goal()])['status'], 'insufficient_data')

    def test_unknown_negative_type_blocks_instead_of_inflating_headroom(self):
        sample = customer()
        sample._transactions.loc[sample._transactions.transaction_type == 'transfer', 'transaction_type'] = 'unknown_debit'
        result = automatic_budget(sample, [goal()])
        self.assertEqual(result['status'], 'insufficient_data')
        self.assertIsNone(result['daily_eur'])
        self.assertIn('unclassified_debit_evidence:2024-01', result['missing_inputs'])

    def test_no_lookahead_and_no_state_mutation(self):
        sample = customer()
        before = sample.get_transactions()
        goals = [goal()]
        targets = deepcopy(goals)
        result = automatic_budget(sample, goals, date(2024, 3, 15))
        self.assertEqual(result['status'], 'insufficient_data')
        self.assertEqual(result['source_period']['end'], '2024-02-29')
        self.assertTrue(sample.get_transactions().equals(before))
        self.assertEqual(goals[0].amount_eur, targets[0].amount_eur)

    def test_http_profiles_and_manual_plan_preserved(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), patch('backend.main.load_customers',
                return_value=[customer(), customer(spend=1100, customer_id="CUST00001")]), TestClient(app) as client:
            other = '/api/customers/CUST00001'
            other_before = {k: client.get(other + '/' + k).json() for k in ['goals', 'assumptions', 'budget']}
            base = '/api/customers/CUST04457'
            self.assertEqual(client.get(base + '/automatic-demo-budget').json()['status'], 'needs_goal')
            client.post(base + '/goals', json={'name': 'Trip', 'amount_eur': '1000', 'priority': 'flexible'})
            before = {k: client.get(base + '/' + k).json() for k in ['goals', 'assumptions', 'budget']}
            result = client.get(base + '/automatic-demo-budget')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['monthly_extra_eur'], 150)
            for key, value in before.items():
                self.assertEqual(client.get(base + '/' + key).json(), value)
            for key, value in other_before.items():
                self.assertEqual(client.get(other + '/' + key).json(), value)
            client.post(other + '/goals', json={'name': 'Bike', 'amount_eur': '100', 'priority': 'critical'})
            other_result = client.get(other + '/automatic-demo-budget').json()
            self.assertEqual(other_result['customer_id'], 'CUST00001')
            self.assertEqual(other_result['monthly_extra_eur'], 0)
            self.assertEqual(client.get(base + '/automatic-demo-budget').json()['monthly_extra_eur'], 150)
            self.assertEqual(client.get('/api/customers/unknown/automatic-demo-budget').status_code, 404)


@skipUnless(os.environ.get('SBANK_DATA_DIR'), 'Set SBANK_DATA_DIR for real demo profile checks')
class RealAutomaticTests(TestCase):
    def test_both_profiles_against_independent_oracle(self):
        for sample in load_customers(os.environ['SBANK_DATA_DIR']):
            result = automatic_budget(sample, [goal()], date(2026, 11, 14))
            self.assertEqual(result['status'], 'estimated', (sample.customer_id, result['missing_inputs']))
            rows = sample.get_transactions()
            dates = rows.tx_date.dt.strftime('%Y-%m-%d')
            rows = rows[dates.between(result['source_period']['start'], result['source_period']['end'])]
            earned = rows[(rows.tx_amount_eur > 0) & rows.transaction_type.isin(['salary', 'income', 'salary_payment', 'pension'])]
            spent = rows[(rows.tx_amount_eur < 0) & rows.transaction_type.isin(['purchase', 'housing_payment', 'utilities_payment'])]
            expected_income = round(sum(Decimal(str(x)) for x in earned.tx_amount_eur) / 3, 2)
            expected_spending = round(-sum(Decimal(str(x)) for x in spent.tx_amount_eur) / 3, 2)
            self.assertEqual(Decimal(str(result['income_eur'])), expected_income)
            self.assertEqual(Decimal(str(result['protected_spending_eur'])), expected_spending)
            self.assertLessEqual(result['goal_allocated_eur'], result['goal_budget_eur'])
            self.assertEqual(result['period_count'], 3)
            self.assertIsNone(automatic_budget(sample, [])['daily_eur'])


if __name__ == '__main__':
    main()
