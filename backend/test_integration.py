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
                def ask(question, scenario=None):
                    response = self.client.post(f'{base}/coach', json={'question': question, 'scenario': scenario})
                    self.assertEqual(response.status_code, 200)
                    return response.json()

                unknown = ask('Daily and weekly allowance')
                self.assertIn('Confirm on Home', unknown['text'])
                self.assertNotIn('EUR', unknown['text'])
                unknown_preview = ask('what if', {'name': 'Unknown plan', 'amount_eur': '100', 'priority': 'important'})
                self.assertIsNone(unknown_preview['analysis']['daily_eur'])
                self.assertEqual(self.client.get(f'{base}/goals').json(), [])
                self.assertIn('unknown', ask('Current account balance')['text'])
                spending = self.client.get(f'{base}/spending').json()
                history = self.client.get(f'{base}/spending-history').json()
                latest = next(p for p in history['periods'] if p['period'] == spending['month'])
                self.assertEqual(latest['spending_eur'], spending['spending_eur'])
                categories = ask('Spending by category')
                self.assertEqual({row['label']: row['value'] for row in categories['rows']}, latest['categories'])
                if latest['categories']:
                    name = next(iter(latest['categories']))
                    category_answer = ask(f'How much on {name}?')
                    self.assertEqual(category_answer['kind'], 'categories')
                    self.assertIn({'label': name, 'value': latest['categories'][name]}, category_answer['rows'])
                average = ask('Spending vs historical average')
                self.assertEqual(average['kind'], 'average')
                if history['historical_average_eur'] is not None:
                    self.assertIn(f"EUR {history['historical_average_eur']:,.2f}", average['text'])
                self.assertEqual(self.client.get(f'{base}/income').status_code, 200)
                mortgage = self.client.get(f'{base}/mortgages').json()
                self.assertEqual(bool(mortgage['applications']), customer['has_mortgage_data'])
                self.assertTrue(all(m['monthly_payment_eur'] is None for m in mortgage['applications']))
                mortgage_answer = ask('What is my mortgage monthly payment?')
                self.assertEqual(mortgage_answer['kind'], 'mortgage')
                self.assertIn('Monthly repayments are unknown', mortgage_answer['text'])
                self.assertEqual(mortgage_answer['text'].startswith('Linked'), customer['has_mortgage_data'])
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
                self.assertIn('EUR 3.33/day', ask('daily allowance')['text'])
                self.assertIn('saved progress is unknown', ask('goal progress')['text'])
                scenario = {'name': 'Confirmed scenario', 'amount_eur': '100.00', 'priority': 'critical'}
                assumptions_before = self.client.get(f'{base}/assumptions').json()
                other_id = 'CUST00001' if customer['customer_id'] == 'CUST04457' else 'CUST04457'
                other_base = f'/api/customers/{other_id}'
                other_goals = self.client.get(f'{other_base}/goals').json()
                # Pin the original-data demo recipe and verify previews with a confirmed, nonzero plan.
                restaurant_demo = {
                    'CUST04457': ('2026-07-01', 95.04, 76.03, 19.01),
                    'CUST00001': ('2026-09-01', 225.70, 180.56, 45.14),
                }
                month_start, restaurant_baseline, hypothetical, reduction = restaurant_demo[customer['customer_id']]
                reduction_payload = dict(category='Restaurants', period='month', period_start=month_start, reduction_percent=20)
                other_inputs = self.client.get(f'{other_base}/assumptions').json()
                other_budget = self.client.get(f'{other_base}/budget').json()
                for percentage in [0, 20, 100, 20]:
                    response = self.client.post(f'{base}/category-reduction', json={
                        **reduction_payload, 'reduction_percent': percentage,
                    })
                    self.assertEqual(response.status_code, 200)
                    reduced = response.json()
                    self.assertEqual(reduced['baseline_spending_eur'], restaurant_baseline)
                    expected = {0: (restaurant_baseline, 0), 20: (hypothetical, reduction), 100: (0, restaurant_baseline)}
                    self.assertEqual((reduced['hypothetical_spending_eur'], reduced['potential_reduction_eur']), expected[percentage])
                    self.assertIsNone(reduced['goal_impact'])
                    self.assertTrue(reduced['read_only'])
                for changes, status in [
                    ({'reduction_percent': -1}, 422), ({'reduction_percent': 101}, 422),
                    ({'reduction_percent': 'NaN'}, 422), ({'category': 'No such category'}, 404),
                    ({'period_start': '2024-10-01'}, 422),  # Both original files begin after October 1.
                ]:
                    response = self.client.post(f'{base}/category-reduction', json={**reduction_payload, **changes})
                    self.assertEqual(response.status_code, status)
                if customer['customer_id'] == 'CUST04457':
                    absent = self.client.post(f'{base}/category-reduction', json={
                        **reduction_payload, 'period_start': '2026-08-01',
                    })
                    self.assertEqual(absent.status_code, 404)
                self.assertEqual(self.client.get(f'{base}/goals').json(), before)
                self.assertEqual(self.client.get(f'{base}/assumptions').json(), assumptions_before)
                self.assertEqual(self.client.get(f'{base}/budget').json(), budget)
                self.assertEqual(self.client.get(f'{other_base}/goals').json(), other_goals)
                self.assertEqual(self.client.get(f'{other_base}/assumptions').json(), other_inputs)
                self.assertEqual(self.client.get(f'{other_base}/budget').json(), other_budget)
                for _ in range(2):
                    simulated = ask('Preview this goal', scenario)
                    self.assertEqual(simulated['preview'], scenario)
                    self.assertEqual(simulated['baseline'], budget)
                    self.assertEqual(simulated['analysis']['allocations'][1]['goal_id'], 'preview')
                    self.assertEqual(simulated['analysis']['allocations'][1]['allocated_eur'], 100)
                    self.assertEqual(self.client.get(f'{base}/goals').json(), before)
                    self.assertEqual(self.client.get(f'{base}/budget').json(), budget)
                    self.assertEqual(self.client.get(f'{base}/assumptions').json(), assumptions_before)
                invalid_preview = self.client.post(f'{base}/coach', json={
                    'question': 'preview', 'scenario': {**scenario, 'amount_eur': '-1'},
                })
                self.assertEqual(invalid_preview.status_code, 422)
                self.assertEqual(self.client.get(f'{base}/goals').json(), before)
                confirmed = self.client.post(f'{base}/goals', json=simulated['preview'])
                self.assertEqual(confirmed.status_code, 201)
                self.assertEqual(len(self.client.get(f'{base}/goals').json()), len(before) + 1)
                self.assertEqual(self.client.get(f'{other_base}/goals').json(), other_goals)
                actual = self.client.get(f'{base}/goal-analysis').json()
                self.assertEqual(actual['daily_eur'], simulated['analysis']['daily_eur'])
                self.assertEqual([a['allocated_eur'] for a in actual['allocations']],
                                 [a['allocated_eur'] for a in simulated['analysis']['allocations']])
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
            self.assertEqual(len(self.client.get(f'{base}/goals').json()), 4)
        self.assertEqual(self.client.get('/api/customers/unknown/assumptions').status_code, 404)
        self.assertEqual(self.client.post('/api/customers/unknown/coach', json={'question': 'goals'}).status_code, 404)
        self.assertEqual(self.client.post(f'{base}/coach', json={'question': '   '}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
