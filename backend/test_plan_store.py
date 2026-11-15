import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.test_data_coach import fixture


class PlanStoreTests(unittest.TestCase):
    def test_confirmed_plan_survives_restart_and_customers_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'COACH_LLM_ENABLED': 'false', 'SBANK_PLAN_STATE_PATH': str(Path(directory) / 'plans.sqlite3')}), \
                patch('backend.main.load_customers', return_value=[fixture(), fixture('CUST00001')]):
            base = '/api/customers/CUST04457/'
            with TestClient(app) as client:
                self.assertFalse(client.get(base + 'planning-state').json()['has_saved_plan'])
                payload = client.get(base + 'assumptions').json()
                payload.update(confirmed_income_eur='3123.45', horizon_days=60, repeat_plan=True,
                               weekly_budget_eur='100', monthly_budget_eur='420', voluntary_goal_contribution_eur='0')
                self.assertEqual(client.put(base + 'assumptions', json=payload).status_code, 200)
                self.assertTrue(client.get(base + 'planning-state').json()['has_saved_plan'])
            with TestClient(app) as client:
                self.assertEqual(client.get(base + 'assumptions').json(), payload)
                self.assertTrue(client.get(base + 'planning-state').json()['has_saved_plan'])
                self.assertFalse(client.get('/api/customers/CUST00001/planning-state').json()['has_saved_plan'])
                self.assertEqual(client.get('/api/customers/missing/planning-state').status_code, 404)
                bad = {**payload, 'horizon_days': 0}
                self.assertEqual(client.put(base + 'assumptions', json=bad).status_code, 422)
                self.assertEqual(client.get(base + 'assumptions').json(), payload)
