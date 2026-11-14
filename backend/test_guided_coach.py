"""Guided savings and goal explanations use real Python calculations with no paid calls."""
from copy import deepcopy
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.coach import goal_message
from backend.financial import plan
from backend.main import app
from backend.savings_demo import savings_opportunities
from backend.test_data_coach import fixture
from backend import test_financial
from backend.test_savings_demo import sample


class GuidedSavingsTests(unittest.TestCase):
    def test_same_month_percentage_results_and_exclusions(self):
        for percent, expected in [(0, (95.04, 0)), (10, (85.54, 9.50)), (20, (76.03, 19.01)), (100, (0, 95.04))]:
            result = savings_opportunities(sample(), '2024-04', percent)
            self.assertEqual(result['status'], 'available')
            self.assertEqual(result['source_period'], {'start': '2024-04-01', 'end': '2024-04-30'})
            restaurants = next(item for item in result['candidates'] if item['category'] == 'restaurants')
            self.assertEqual(restaurants['baseline_spending_eur'], 95.04)
            self.assertEqual((restaurants['hypothetical_spending_eur'], restaurants['potential_reduction_eur']), expected)
            self.assertEqual(len(result['candidates']), 3)
            serialized = json.dumps(result)
            for private in ['9999', 'Private Merchant', 'private-account', 'CUST04457']:
                self.assertNotIn(private, serialized)

    def test_unavailable_period_and_no_candidates_are_distinct(self):
        customer = sample()
        self.assertEqual(savings_opportunities(customer, '2024-05')['status'], 'unavailable_period')
        customer._transactions.loc[customer._transactions.transaction_type == 'purchase', 'category'] = 'Groceries'
        result = savings_opportunities(customer)
        self.assertEqual(result['status'], 'no_candidates')
        self.assertEqual(result['source_period']['start'], '2024-04-01')
        self.assertEqual(result['candidates'], [])

    def test_http_validation_and_repeated_reads_never_mutate_or_call_provider(self):
        service = SimpleNamespace(close=AsyncMock(), respond=AsyncMock(side_effect=AssertionError('No Coach call')))
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), \
                patch('backend.main.load_customers', return_value=[sample()]), \
                patch('backend.coach_llm.CoachLLM.from_env', return_value=service):
            with TestClient(app) as client:
                base = '/api/customers/CUST04457/'
                client.post(base + 'goals', json={'name': 'Trip', 'amount_eur': '300', 'priority': 'flexible'})
                before = {key: client.get(base + key).json() for key in ['goals', 'assumptions', 'goal-analysis', 'budget']}
                for percent in [0, 10, 20, 100, 10]:
                    response = client.get(base + 'savings-opportunities', params={'month': '2024-04', 'reduction_percent': percent})
                    self.assertEqual(response.status_code, 200)
                for query in ['reduction_percent=-1', 'reduction_percent=101', 'reduction_percent=NaN',
                              'reduction_percent=10.123', 'month=2024-13', 'month=last-month']:
                    self.assertEqual(client.get(base + 'savings-opportunities?' + query).status_code, 422)
                self.assertEqual(client.get('/api/customers/missing/savings-opportunities').status_code, 404)
                after = {key: client.get(base + key).json() for key in before}
                self.assertEqual(before, after)
                service.respond.assert_not_awaited()


class GuidedGoalTests(unittest.TestCase):
    def setUp(self):
        self.inputs = test_financial.FinancialTests().assumptions()
        self.goals = [SimpleNamespace(id='flex', name='Trip', amount_eur=200, priority='flexible'),
                      SimpleNamespace(id='critical', name='Repair', amount_eur=200, priority='critical')]

    def test_missing_inputs_and_no_goals_do_not_claim_feasibility(self):
        text = goal_message(plan({}, self.goals), self.goals)
        self.assertIn('cannot yet say', text)
        self.assertIn('do not count income already in that balance again', text)
        self.assertNotIn('EUR', text)
        self.assertIn('Nothing is saved until you confirm', goal_message(plan({}, []), []))

    def test_priority_allocations_and_conditional_timing_are_explained(self):
        analysis = plan(self.inputs, self.goals)
        before = deepcopy(analysis)
        text = goal_message(analysis, self.goals)
        self.assertIn('Repair: EUR 200.00 planned towards EUR 200.00 - this target fits', text)
        self.assertIn('Trip: EUR 100.00 planned towards EUR 200.00 - not fully funded', text)
        self.assertIn('2 plan periods of 30 days if', text)
        self.assertLess(text.index('Repair:'), text.index('Trip:'))
        self.assertIn('saved progress is unknown', text)
        self.assertEqual(analysis, before)

    def test_no_repeating_plan_or_zero_capacity_does_not_promise_completion(self):
        for changes in [{'repeat_plan': False}, {'available_funds_eur': 0}, {'voluntary_goal_contribution_eur': 0}]:
            inputs = {**self.inputs, **changes}
            text = goal_message(plan(inputs, self.goals), self.goals)
            self.assertNotIn('conditionally reachable', text)
            self.assertIn('not fully funded', text)
            self.assertIn('Possible historical cuts have not been added', text)
        text = goal_message(plan({**self.inputs, 'available_funds_eur': 0}, self.goals), self.goals)
        self.assertIn('exceed confirmed funds by EUR 600.00', text)


if __name__ == '__main__':
    unittest.main()
