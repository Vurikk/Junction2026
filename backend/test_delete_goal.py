import os
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app
from backend.test_automatic_demo_budget import customer


class DeleteGoalTests(TestCase):
    def test_delete_is_customer_scoped_and_recalculates_plan(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false', 'SBANK_PLAN_STATE_PATH': ''}), \
                patch('backend.main.load_customers', return_value=[customer(), customer(customer_id='CUST00001')]), \
                TestClient(app) as client:
            base = '/api/customers/CUST04457/'
            goal = client.post(base + 'goals', json={
                'name': 'Trip', 'amount_eur': '1000', 'priority': 'critical'}).json()
            other = '/api/customers/CUST00001/goals/' + goal['id']
            self.assertEqual(client.delete(other).status_code, 404)
            self.assertEqual(len(client.get(base + 'goals').json()), 1)
            before = client.get(base + 'goal-plan').json()
            self.assertEqual(client.delete(base + 'goals/' + goal['id']).status_code, 200)
            self.assertEqual(client.get(base + 'goals').json(), [])
            after = client.get(base + 'goal-plan').json()
            self.assertGreater(after['monthly_extra_eur'], before['monthly_extra_eur'])
            self.assertEqual(after['goals'], [])
            self.assertEqual(client.get(base + 'automatic-demo-budget').json()['status'], 'needs_goal')
            self.assertIsNone(client.get(base + 'spending-history').json()['budget_target_eur'])
            self.assertEqual(client.delete(base + 'goals/' + goal['id']).status_code, 404)
            self.assertEqual(client.delete('/api/customers/missing/goals/' + goal['id']).status_code, 404)
