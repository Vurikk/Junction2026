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
    def test_target_warning_uses_latest_complete_month_and_thresholds(self):
        sample = customer()
        self.assertEqual(automatic_budget(sample, [goal()])['target_comparison']['status'], 'within')
        rows = sample._transactions
        latest = (rows.transaction_type == 'purchase') & (rows.tx_amount_eur == -600)
        index = rows[latest].index[-1]
        rows.loc[index, 'tx_amount_eur'] = -750
        self.assertEqual(automatic_budget(sample, [goal()])['target_comparison']['status'], 'near')
        rows.loc[index, 'tx_amount_eur'] = -1000
        result = automatic_budget(sample, [goal()])['target_comparison']
        self.assertEqual(result['status'], 'over')
        self.assertEqual(result['over_eur'], 183.33)
        self.assertEqual(result['period'], {'start': '2024-03-01', 'end': '2024-03-31'})
        self.assertIsNone(automatic_budget(sample, [])['target_comparison'])

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


class ChartTargetTests(TestCase):
    def test_manual_zero_and_matching_period_precedence(self):
        from backend.automatic_demo_budget import chart_target
        for period in ['week', 'month']:
            value, metadata = chart_target(customer(), [], '0.00', period)
            self.assertEqual(value, '0.00')
            self.assertEqual(metadata['target_source'], 'manual')
            self.assertIsNone(metadata['target_source_period'])

    def test_total_spending_exact_units_and_goal_changes(self):
        from backend.automatic_demo_budget import chart_target
        sample = customer()
        monthly, metadata = chart_target(sample, [goal()], None, 'month')
        self.assertEqual(monthly, 750)
        weekly, _ = chart_target(sample, [goal()], None, 'week')
        self.assertEqual(weekly, 173.07)
        self.assertEqual(metadata['target_source'], 'automatic_historical')
        self.assertEqual(metadata['target_source_period'], {'start': '2024-01-01', 'end': '2024-03-31'})
        changed, _ = chart_target(sample, [goal(20)], None, 'month')
        self.assertEqual(changed, 880)
        for period in ['week', 'month']:
            self.assertIsNone(chart_target(sample, [], None, period)[0])
        sample._transactions = sample._transactions.iloc[0:0].copy()
        self.assertIsNone(chart_target(sample, [goal()], None, 'week')[0])

    def test_http_manual_zero_matching_period_and_nonmutation(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), patch('backend.main.load_customers',
                return_value=[customer()]), TestClient(app) as client:
            base = '/api/customers/CUST04457'
            for period in ['week', 'month']:
                result = client.get(base + '/spending-history', params={'period': period}).json()
                self.assertIsNone(result['budget_target_eur'])
                self.assertIsNone(result['target_source'])
            client.post(base + '/goals', json={'name': 'Trip', 'amount_eur': '1000', 'priority': 'critical'})
            before = {k: client.get(base + '/' + k).json() for k in ['goals', 'assumptions', 'budget']}
            for period, expected in [('week', 173.07), ('month', 750)]:
                result = client.get(base + '/spending-history', params={'period': period}).json()
                self.assertEqual(result['budget_target_eur'], expected)
                self.assertEqual(result['target_source'], 'automatic_historical')
                self.assertTrue(all(p['budget_target_eur'] == expected for p in result['periods']))
            for key, value in before.items():
                self.assertEqual(client.get(base + '/' + key).json(), value)
            client.put(base + '/assumptions', json={'weekly_budget_eur': '0.00'})
            weekly = client.get(base + '/spending-history', params={'period': 'week'}).json()
            monthly = client.get(base + '/spending-history', params={'period': 'month'}).json()
            self.assertEqual(weekly['target_source'], 'manual')
            self.assertEqual(Decimal(str(weekly['budget_target_eur'])), 0)
            self.assertEqual(monthly['target_source'], 'automatic_historical')


if __name__ == '__main__':
    main()
