"""Real HTTP integration against an isolated Uvicorn process and local demo data."""

import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import httpx


class LiveIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        cls.log = tempfile.TemporaryFile(mode='w+')
        cls.process = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', str(port)],
            cwd=Path(__file__).resolve().parents[1], stdout=cls.log, stderr=cls.log,
        )
        cls.client = httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30, trust_env=False)
        cls.addClassCleanup(cls.cleanup)
        for _ in range(120):
            if cls.process.poll() is not None:
                cls.log.seek(0)
                raise RuntimeError(cls.log.read())
            try:
                if cls.client.get('/api/health').status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.25)
        raise RuntimeError('Isolated API server did not become ready')

    @classmethod
    def cleanup(cls):
        cls.client.close()
        cls.process.terminate()
        cls.process.wait(timeout=15)
        cls.log.close()

    def test_complete_workflow_for_both_customers(self):
        customers = self.client.get('/api/customers').json()
        self.assertEqual([c['customer_id'] for c in customers], ['CUST04457', 'CUST00001'])
        for customer in customers:
            with self.subTest(customer=customer['customer_id']):
                base = f"/api/customers/{customer['customer_id']}"
                self.assertEqual(self.client.get(f'{base}/goals').json(), [])
                initial = self.client.get(f'{base}/budget').json()
                self.assertEqual(initial['status'], 'insufficient_data')
                self.assertIsNone(initial['daily_eur'])
                spending = self.client.get(f'{base}/spending').json()
                history = self.client.get(f'{base}/spending-history').json()
                latest = next(p for p in history['periods'] if p['period'] == spending['month'])
                self.assertEqual(latest['spending_eur'], spending['spending_eur'])
                self.assertEqual(self.client.get(f'{base}/income').status_code, 200)
                mortgage = self.client.get(f'{base}/mortgages').json()
                self.assertEqual(bool(mortgage['applications']), customer['has_mortgage_data'])
                ids = {}
                for priority in ['flexible', 'important', 'critical']:
                    response = self.client.post(f'{base}/goals', json={
                        'name': f'{priority} integration goal', 'amount_eur': '200.00', 'priority': priority,
                    })
                    self.assertEqual(response.status_code, 201)
                    ids[priority] = response.json()['id']
                inputs = dict(available_funds_eur='1000.00', confirmed_income_eur='0.00',
                              upcoming_essential_bills_eur='400.00', emergency_reserve_eur='200.00',
                              everyday_spending_eur='100.00', voluntary_goal_contribution_eur='300.00',
                              horizon_days=30, repeat_plan=True, weekly_budget_eur='70.00', monthly_budget_eur='300.00')
                response = self.client.put(f'{base}/assumptions', json=inputs)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.get(f'{base}/assumptions').json(), inputs)
                budget = self.client.get(f'{base}/budget').json()
                self.assertEqual(budget['status'], 'estimated')
                self.assertEqual(budget['daily_eur'], 3.33)
                self.assertEqual(budget['weekly_eur'], 23.31)
                before = self.client.get(f'{base}/goals').json()
                analysis = self.client.get(f'{base}/goal-analysis').json()
                self.assertEqual(analysis['ordered_goal_ids'], [ids[p] for p in ['critical', 'important', 'flexible']])
                self.assertEqual([a['allocated_eur'] for a in analysis['allocations']], [200, 100, 0])
                self.assertEqual([a['completion_periods'] for a in analysis['allocations']], [1, 2, 2])
                self.assertEqual(self.client.get(f'{base}/goals').json(), before)
                for period, target in [('week', 70), ('month', 300)]:
                    chart = self.client.get(f'{base}/spending-history?period={period}').json()
                    self.assertEqual(float(chart['budget_target_eur']), target)
                    for point in chart['periods']:
                        self.assertAlmostEqual(sum(point['baskets'].values()), point['spending_eur'], places=2)
                        self.assertAlmostEqual(point['remaining_budget_eur'], target - point['spending_eur'], places=2)
                invalid = self.client.put(f'{base}/assumptions', json={**inputs, 'available_funds_eur': '-1'})
                self.assertEqual(invalid.status_code, 422)
                self.assertEqual(self.client.get(f'{base}/assumptions').json(), inputs)
                self.assertEqual(self.client.get(f'{base}/spending-history?period=day').status_code, 422)
                inputs['repeat_plan'] = False
                inputs['available_funds_eur'] = '0.00'
                self.client.put(f'{base}/assumptions', json=inputs).raise_for_status()
                deficit = self.client.get(f'{base}/goal-analysis').json()
                self.assertEqual(deficit['daily_eur'], 0)
                self.assertEqual(deficit['shortfall_eur'], 600)
                self.assertTrue(all(a['completion_periods'] is None for a in deficit['allocations']))
                self.client.put(f'{base}/assumptions', json={}).raise_for_status()
                self.assertIsNone(self.client.get(f'{base}/budget').json()['daily_eur'])
        for customer in customers:
            base = f"/api/customers/{customer['customer_id']}"
            self.assertEqual(len(self.client.get(f'{base}/goals').json()), 3)
        self.assertEqual(self.client.get('/api/customers/unknown/assumptions').status_code, 404)


if __name__ == '__main__':
    unittest.main()
