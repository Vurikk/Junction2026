"""Curated demo prompts use actual Python data; no live provider or deployment ledger."""

import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
from fastapi.testclient import TestClient

from backend.coach_llm import CoachLLM
from backend.coach_ledger import Ledger
from backend.verda import identity
from backend.coach_tools import expected_selection, run_tool, sanitize_question
from backend.demo_prompts import demo_prompts
from backend.main import app
from backend.test_data_coach import fixture


class DemoPromptTests(unittest.TestCase):
    def calculate(self, customer, question):
        selected = expected_selection(sanitize_question(question), None, customer)
        return run_tool(customer, selected)

    def test_each_default_prompt_is_supported_and_calculates_actual_fixture_amounts(self):
        customer = fixture()
        before = customer._transactions.copy(deep=True)
        result = demo_prompts(customer)
        prompts = {item['id']: item for item in result['questions']}
        self.assertEqual(set(prompts), {'overview', 'comparison', 'restaurants'})
        self.assertTrue(result['note'])
        for item in prompts.values():
            self.assertEqual(set(item), {'id', 'label', 'question'})
            self.assertTrue(item['label'])
            self.assertLessEqual(len(item['question']), 500)
        overview = self.calculate(customer, prompts['overview']['question'])['data']
        self.assertEqual(overview['source_period']['start'], '2024-04-01')
        self.assertEqual(overview['spending_eur'], 400)
        comparison = self.calculate(customer, prompts['comparison']['question'])['data']
        self.assertEqual(comparison['difference_eur'], 200)
        reduction = self.calculate(customer, prompts['restaurants']['question'])['data']
        self.assertEqual(reduction['reduction_percent'], 20)
        self.assertEqual(reduction['source_period']['start'], '2024-04-01')
        self.assertEqual((reduction['baseline_spending_eur'], reduction['hypothetical_spending_eur'],
                          reduction['potential_reduction_eur']), (400, 320, 80))
        self.assertNotIn('CUST04457', json.dumps(result))
        pd.testing.assert_frame_equal(before, customer._transactions)

    def test_restaurant_prompt_uses_latest_month_with_observations_not_empty_latest(self):
        customer = fixture(records=[
            ('2024-04-01', 'transfer', 0, 'transfer', 'private-account', 100),
            ('2024-04-15', 'purchase', -95.04, 'Restaurants', 'private-account', 100),
            ('2024-05-15', 'purchase', -30, 'Groceries', 'private-account', 100),
            ('2024-05-31', 'transfer', 0, 'transfer', 'private-account', 100),
        ])
        prompts = {item['id']: item for item in demo_prompts(customer)['questions']}
        overview = self.calculate(customer, prompts['overview']['question'])['data']
        restaurant = self.calculate(customer, prompts['restaurants']['question'])['data']
        self.assertEqual(overview['source_period']['start'], '2024-05-01')
        self.assertEqual(restaurant['source_period']['start'], '2024-04-01')
        self.assertEqual(restaurant['potential_reduction_eur'], 19.01)
        self.assertNotIn('private-account', json.dumps(prompts))

    def test_empty_or_partial_history_never_invents_a_demo_period(self):
        empty = fixture()
        empty._transactions = empty._transactions.iloc[:0].copy()
        partial = fixture(records=[('2024-04-15', 'purchase', -20, 'Restaurants', 'one', 0)])
        for customer in (empty, partial):
            with self.subTest(empty=customer._transactions.empty):
                result = demo_prompts(customer)
                self.assertEqual(result['questions'], [])
                self.assertTrue(result['note'])

    def test_one_full_month_without_restaurants_omits_unsupported_prompts(self):
        customer = fixture(records=[
            ('2024-04-01', 'transfer', 0, 'transfer', 'one', 0),
            ('2024-04-15', 'purchase', -20, 'Groceries', 'one', 0),
            ('2024-04-30', 'transfer', 0, 'transfer', 'one', 0),
        ])
        result = demo_prompts(customer)
        self.assertEqual([item['id'] for item in result['questions']], ['overview'])
        self.assertEqual(self.calculate(customer, result['questions'][0]['question'])['data']['spending_eur'], 20)

    def test_get_prompts_is_read_only_and_unknown_customer_is_404(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), \
                patch('backend.main.load_customers', return_value=[fixture()]):
            with TestClient(app) as client:
                base = '/api/customers/CUST04457'
                before = {name: client.get(base + '/' + name).json() for name in ('goals', 'assumptions', 'budget')}
                response = client.get(base + '/coach-demo-prompts')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), demo_prompts(app.state.customers['CUST04457']))
                self.assertEqual(client.get('/api/customers/unknown/coach-demo-prompts').status_code, 404)
                for name, value in before.items():
                    self.assertEqual(client.get(base + '/' + name).json(), value)

    def test_common_demo_guidance_never_uses_provider_or_reservations(self):
        ledger = Mock()
        ledger.conversation.return_value = None
        ledger.claim.return_value = None
        provider = SimpleNamespace(settings=SimpleNamespace(ledger=ledger), complete=AsyncMock(), close=AsyncMock())
        service = CoachLLM(provider)
        questions = ['How can I save money?', 'How can I save?', 'Where can I save money?',
                     'From what categories would be easy to save from?', 'What categories can I save on?']
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), \
                patch('backend.main.load_customers', return_value=[fixture()]), \
                patch('backend.coach_llm.CoachLLM.from_env', return_value=service):
            with TestClient(app) as client:
                base = '/api/customers/CUST04457'
                before = {name: client.get(base + '/' + name).json() for name in ('goals', 'assumptions', 'budget')}
                boot = client.post(base + '/coach', json={'question': 'Spending by category'}).json()
                for question in questions:
                    with self.subTest(question=question):
                        result = client.post(base + '/coach', json={'question': question,
                            'conversation_id': boot['conversation_id'], 'request_id': str(uuid4())}).json()
                        self.assertEqual(result['mode'], 'rule_based')
                        self.assertEqual(result['fallback_reason'], 'demo_guidance')
                        self.assertEqual(result['kind'], 'help')
                        self.assertTrue(result['text'])
                        self.assertEqual(result['cards'], [])
                provider.complete.assert_not_awaited()
                ledger.reserve.assert_not_called()
                self.assertEqual(ledger.finish.call_count, len(questions))
                for name, value in before.items():
                    self.assertEqual(client.get(base + '/' + name).json(), value)


class GuidanceIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger = Ledger.initialize(Path(self.directory.name) / 'usage.sqlite3', identity())
        self.provider = SimpleNamespace(settings=SimpleNamespace(ledger=self.ledger),
                                        complete=AsyncMock(side_effect=AssertionError('No provider call allowed')))
        self.service = CoachLLM(self.provider)
        self.conversation = str(uuid4())
        self.customer = fixture()

    async def ask(self, question, request_id, *, session='browser', customer=None):
        return await self.service.respond(customer or self.customer, question, self.conversation,
                                          request_id, session, {'kind': 'help', 'text': 'Fallback', 'rows': []})

    async def test_guidance_replay_conflicts_and_owner_checks(self):
        request_id = str(uuid4())
        first = await self.ask('How can I save money?', request_id)
        self.assertEqual(first['fallback_reason'], 'demo_guidance')
        self.assertEqual(await self.ask('How can I save money?', request_id), first)
        for question in ['Where can I save money?', 'Reduce restaurants in April 2024 by 20%']:
            conflict = await self.ask(question, request_id)
            self.assertEqual(conflict['fallback_reason'], 'request_conflict')
        for kwargs in [{'session': 'other-browser'}, {'customer': fixture('CUST00001')}]:
            denied = await self.ask('How can I save money?', str(uuid4()), **kwargs)
            self.assertEqual(denied['fallback_reason'], 'conversation_mismatch')
        self.provider.complete.assert_not_awaited()
        self.assertEqual(self.ledger.spent(), 0)
        with self.ledger.transaction() as (db, _):
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM calls').fetchone()[0], 0)

    async def test_guidance_cannot_replace_an_existing_calculation_identity(self):
        # Ambiguous financial request is a durable, zero-cost receipt in the normal paid-capable path.
        request_id = str(uuid4())
        original = await self.ask('Food', request_id)
        self.assertEqual(original['fallback_reason'], 'clarification_needed')
        denied = await self.ask('How can I save money?', request_id)
        self.assertEqual(denied['fallback_reason'], 'request_conflict')
        self.assertEqual(await self.ask('Food', request_id), original)
        self.provider.complete.assert_not_awaited()
        self.assertEqual(self.ledger.spent(), 0)

    async def test_disabled_guidance_keeps_local_identity_and_reduction_context(self):
        self.service = CoachLLM()
        first = await self.ask('Reduce restaurants in April 2024 by 20%', str(uuid4()))
        self.assertEqual(first['cards'][0]['data']['potential_reduction_eur'], 80)
        request_id = str(uuid4())
        guidance = await self.ask('How can I save money?', request_id)
        self.assertEqual(guidance['fallback_reason'], 'demo_guidance')
        self.assertEqual(await self.ask('How can I save money?', request_id), guidance)
        conflict = await self.ask('Where can I save money?', request_id)
        self.assertEqual(conflict['fallback_reason'], 'request_conflict')
        denied = await self.ask('How can I save money?', str(uuid4()), session='other-browser')
        self.assertEqual(denied['fallback_reason'], 'conversation_mismatch')
        followup = await self.ask('What about 10% instead?', str(uuid4()))
        self.assertEqual(followup['cards'][0]['data']['potential_reduction_eur'], 40)


if __name__ == '__main__':
    unittest.main()
