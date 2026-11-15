from copy import deepcopy
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.guided_demo import answer
from backend.main import app, Goal
from backend.test_data_coach import fixture
from backend.test_automatic_demo_budget import customer


class GuidedDemoTests(TestCase):
    def test_savings_followup_keeps_month_and_exact_python_values(self):
        first = answer(fixture(), [], 'savings')
        self.assertEqual(first['source_period']['start'], '2024-04-01')
        self.assertEqual(first['rows'][0]['value'], 40)
        follow = first['actions'][0]
        second = answer(fixture(), [], follow['action'], follow['percent'], follow['month'], follow['category'])
        self.assertEqual(second['rows'][0]['value'], 80)
        self.assertIn('320.00', second['rows'][0]['detail'])
        unavailable = answer(fixture(), [], 'savings', month='2026-10')
        self.assertEqual(unavailable['rows'], [])

    def test_savings_chart_matches_answer_and_preserves_selected_scenario(self):
        for percent in [10, 20]:
            result = answer(fixture(), [], 'savings', percent=percent)
            chart = result['savings_projection']
            self.assertEqual(chart['percent'], percent)
            self.assertEqual(len(chart['points']), 7)
            for series, row in zip(chart['series'], result['rows']):
                self.assertEqual(chart['points'][0][series['key']], 0)
                self.assertEqual(chart['points'][1][series['key']], row['value'])
                self.assertEqual(Decimal(str(chart['points'][6][series['key']])), Decimal(str(row['value'])) * 6)
            self.assertIn('Hypothetical', chart['note'])
        self.assertNotIn('savings_projection', answer(fixture(), [], 'savings', month='2026-10'))

    def test_goals_are_conditional_and_never_claim_saved_progress(self):
        goal = Goal(id='one', customer_id='CUST04457', name='Guitar', amount_eur=Decimal('1000'), priority='critical')
        result = answer(customer(), [goal], 'goals')
        self.assertEqual(result['rows'][0]['value'], 150)
        self.assertIn('7 months only if', result['rows'][0]['detail'])
        blocked = answer(customer(spend=1100), [goal], 'goals')
        self.assertEqual(blocked['rows'][0]['value'], 0)
        self.assertIn('unknown', blocked['rows'][0]['detail'])
        self.assertIn('Create a goal', answer(customer(), [], 'goals')['text'])

    def test_http_all_choices_are_read_only_and_never_use_provider(self):
        with patch.dict('os.environ', {'COACH_LLM_ENABLED': 'false'}), \
                patch('backend.main.load_customers', return_value=[customer(), customer(customer_id='CUST00001')]):
            with TestClient(app) as client:
                created = client.post('/api/customers/CUST04457/goals', json={
                    'name': 'Guitar', 'amount_eur': '1000', 'priority': 'critical'})
                self.assertEqual(created.status_code, 201)
                before = deepcopy((app.state.assumptions, app.state.goals))
                with patch.object(app.state.coach_llm, 'respond', side_effect=AssertionError('LLM must not run')):
                    for action in ['savings', 'overview', 'goals', 'comparison', 'allowance', 'tips']:
                        response = client.post('/api/customers/CUST04457/guided-coach', json={'action': action})
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertEqual(response.json()['mode'], 'guided')
                    other = client.post('/api/customers/CUST00001/guided-coach', json={'action': 'goals'})
                    self.assertIn('Create a goal', other.json()['text'])
                    self.assertEqual(client.post('/api/customers/CUST04457/guided-coach',
                                                 json={'action': 'anything'}).status_code, 422)
                    self.assertEqual(client.post('/api/customers/unknown/guided-coach',
                                                 json={'action': 'goals'}).status_code, 404)
                self.assertEqual(before, (app.state.assumptions, app.state.goals))
