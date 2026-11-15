from copy import deepcopy
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.automatic_demo_budget import automatic_budget
from backend.goal_plan import goal_plan, preview_goal
from backend.main import app, Goal
from backend.test_automatic_demo_budget import customer


def goal(name, amount, priority='flexible'):
    return Goal(id=name, customer_id='CUST04457', name=name, amount_eur=Decimal(str(amount)), priority=priority)


class GoalPlanTests(TestCase):
    def test_capacity_without_goal_preserves_home_contract(self):
        profile = customer()
        self.assertEqual(automatic_budget(profile, [])['status'], 'needs_goal')
        result = goal_plan(profile, [])
        self.assertEqual(result['status'], 'estimated')
        self.assertEqual(result['monthly_savings_capacity_eur'], 300)
        self.assertEqual(result['monthly_extra_eur'], 300)
        self.assertEqual(result['goal_allocated_eur'], 0)

    def test_priority_rollover_and_conditional_calendar_weeks(self):
        result = goal_plan(customer(), [goal('later', 100, 'flexible'), goal('first', 1000, 'critical')])
        first, later = result['goals']
        self.assertEqual(first['goal_id'], 'first')
        self.assertEqual(first['monthly_allocation_eur'], 150)
        self.assertEqual(first['completion_months'], 7)
        self.assertEqual(first['completion_weeks'], 31)
        self.assertEqual(later['monthly_allocation_eur'], 0)
        self.assertEqual(later['completion_months'], 8)
        self.assertEqual(later['save_all_extra_months'], 4)
        self.assertEqual(result['monthly_extra_eur'] + result['goal_allocated_eur'], result['monthly_savings_capacity_eur'])

    def test_preview_before_after_matches_home_without_saving(self):
        profile = customer()
        proposed = goal('new', 1000, 'critical')
        result = preview_goal(profile, [], proposed)
        self.assertFalse(result['saved'])
        self.assertEqual(result['spending_change']['monthly_extra_eur'], -150)
        self.assertEqual(result['after']['daily_eur'], automatic_budget(profile, [proposed])['daily_eur'])
        unchanged = preview_goal(profile, [goal('existing', 1000)], goal('urgent', 200, 'critical'))
        self.assertEqual(unchanged['spending_change']['daily_eur'], 0)
        self.assertEqual(unchanged['after']['goals'][0]['name'], 'urgent')

    def test_zero_and_missing_are_distinct_and_no_double_count_of_extra(self):
        no_surplus = goal_plan(customer(spend=1100), [goal('goal', 500)])
        self.assertEqual(no_surplus['monthly_savings_capacity_eur'], 0)
        self.assertIsNone(no_surplus['goals'][0]['completion_months'])
        unknown = customer()
        unknown._transactions = unknown._transactions[unknown._transactions.transaction_type != 'salary']
        missing = goal_plan(unknown, [goal('goal', 500)])
        self.assertIsNone(missing['monthly_savings_capacity_eur'])
        self.assertIsNone(missing['goals'][0]['save_all_extra_months'])

    def test_http_preview_chat_no_provider_no_mutation_and_creation_compatibility(self):
        with patch.dict('os.environ', {'COACH_LLM_ENABLED': 'false'}), \
                patch('backend.main.load_customers', return_value=[customer(), customer(customer_id='CUST00001')]):
            with TestClient(app) as client:
                root = '/api/customers/CUST04457'
                before = deepcopy((app.state.assumptions, app.state.goals))
                payload = {'name': 'Trip', 'amount_eur': '1000', 'priority': 'important'}
                with patch.object(app.state.coach_llm, 'respond', side_effect=AssertionError('No LLM allowed')):
                    preview = client.post(root + '/goal-plan/preview', json=payload)
                    self.assertEqual(preview.status_code, 200)
                    self.assertEqual(client.get(root + '/goal-plan').status_code, 200)
                    for action in ['monthly_savings', 'goal_timing']:
                        self.assertEqual(client.post(root + '/guided-coach', json={'action': action}).status_code, 200)
                    self.assertEqual(before, (app.state.assumptions, app.state.goals))
                    self.assertEqual(client.post(root + '/goal-plan/preview', json={**payload, 'amount_eur': '-1'}).status_code, 422)
                    self.assertEqual(client.get('/api/customers/unknown/goal-plan').status_code, 404)
                    self.assertEqual(client.post(root + '/goals', json=payload).status_code, 201)
                    after = client.get(root + '/goal-plan').json()
                    self.assertEqual(after['daily_eur'], preview.json()['after']['daily_eur'])
                    self.assertEqual(after['goals'][0]['priority_label'], 'Important')
                    self.assertEqual(client.get('/api/customers/CUST00001/goals').json(), [])
