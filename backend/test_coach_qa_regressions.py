"""QA-01/02/03: free date/context correctness and safe readmission of unstarted paid work."""

import asyncio
from datetime import date
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from backend.coach import answer
from backend.coach_ledger import GateError, Ledger
from backend.coach_llm import CoachLLM
from backend.financial import history, plan
from backend.main import app
from backend.test_data_coach import fixture
from backend.test_coach_single_call import envelope
from backend.verda import INPUT_BOUND, OUTPUT_BOUND, Settings, VerdaClient, identity


QUESTION = 'What if I reduce restaurants in April 2024 by 20%?'


class DisabledCoachTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = CoachLLM()
        self.customer = fixture()
        self.conversation = str(uuid4())
        guard = patch.object(Ledger, 'transaction', side_effect=AssertionError('Free mode must not access a paid ledger'))
        guard.start()
        self.addCleanup(guard.stop)

    async def ask(self, question=QUESTION, *, request_id=None, conversation=None, session='browser', customer=None):
        customer = customer or self.customer
        baseline = answer(question, plan({}, []), [], history(customer, 'month'))
        return await self.service.respond(customer, question, conversation or self.conversation,
                                          request_id or str(uuid4()), session, baseline)

    async def test_last_month_and_explicit_unavailable_dates_never_substitute_history(self):
        with patch('backend.coach_tools.today_local', return_value=date(2026, 11, 14)):
            for question in ['How much did I spend on restaurants last month?',
                             'Restaurants in October 2026', 'Restaurants in May 2024']:
                with self.subTest(question=question):
                    result = await self.ask(question)
                    self.assertEqual(result['mode'], 'rule_based')
                    self.assertEqual(result['fallback_reason'], 'unsupported_period_or_category')
                    self.assertIn('requested category and period', result['text'])
                    self.assertEqual(result['cards'], [])
                    self.assertEqual(result['rows'], [])
                    self.assertNotIn('Recorded categories for', result['text'])

    async def test_valid_dates_and_calendar_boundaries(self):
        with patch('backend.coach_tools.today_local', return_value=date(2024, 5, 10)):
            result = await self.ask('Restaurants last month')
            self.assertEqual(result['cards'][0]['data']['source_period']['start'], '2024-04-01')
            self.assertEqual(result['cards'][0]['data']['spending_eur'], 400)
        records = [('2024-12-01', 'transfer', 0, 'transfer', 'one', 0),
                   ('2024-12-25', 'purchase', -12, 'Restaurants', 'one', 0),
                   ('2024-12-31', 'transfer', 0, 'transfer', 'one', 0)]
        with patch('backend.coach_tools.today_local', return_value=date(2025, 1, 1)):
            customer = fixture(records=records)
            month = await self.ask('Restaurants last month', customer=customer)
            week = await self.ask('Restaurants last week', customer=customer)
            self.assertEqual(month['cards'][0]['data']['source_period'], {'start': '2024-12-01', 'end': '2024-12-31'})
            self.assertEqual(week['cards'][0]['data']['source_period'], {'start': '2024-12-23', 'end': '2024-12-29'})
            self.assertEqual(week['cards'][0]['data']['spending_eur'], 12)

    async def test_reduction_followup_and_food_clarification(self):
        first = await self.ask()
        self.assertEqual(first['fallback_reason'], 'disabled')
        self.assertEqual(first['cards'][0]['data']['hypothetical_spending_eur'], 320)
        second = await self.ask('What about 10% instead?')
        data = second['cards'][0]['data']
        self.assertEqual((data['baseline_spending_eur'], data['hypothetical_spending_eur'], data['potential_reduction_eur']),
                         (400, 360, 40))
        self.assertEqual(data['source_period']['start'], '2024-04-01')
        self.assertIn('not actual savings', second['text'])
        self.assertNotIn('Enter a goal', first['text'])
        food = await self.ask('Food', conversation=str(uuid4()))
        self.assertEqual(food['fallback_reason'], 'clarification_needed')
        self.assertEqual(food['text'], 'Do you mean groceries or restaurants?')

    async def test_isolation_and_unsafe_wording_never_restore_stale_rows(self):
        await self.ask()
        for kwargs in [{'session': 'other-browser'}, {'customer': fixture('CUST00001')}]:
            with self.subTest(kwargs=kwargs):
                result = await self.ask('What about 10% instead?', **kwargs)
                self.assertEqual(result['fallback_reason'], 'conversation_mismatch')
                self.assertEqual(result['cards'], [])
        fresh = await self.ask('What about 10% instead?', customer=fixture('CUST00001'), conversation=str(uuid4()))
        self.assertEqual(fresh['fallback_reason'], 'clarification_needed')
        for question in ['Calculate restaurant transactions last month', 'My account FI2112345600000785 restaurants']:
            result = await self.ask(question)
            self.assertEqual(result['fallback_reason'], 'privacy_blocked')
            self.assertEqual(result['cards'], [])
            self.assertEqual(result['rows'], [])

    async def test_identical_replay_conflict_and_no_context_rollback(self):
        request_id = str(uuid4())
        first = await self.ask(request_id=request_id)
        await self.ask('What about 10% in March 2024?')
        self.assertEqual(await self.ask(request_id=request_id), first)
        changed = await self.ask('What about 10% instead?', request_id=request_id)
        self.assertEqual(changed['fallback_reason'], 'request_conflict')
        other_conversation = await self.ask(request_id=request_id, conversation=str(uuid4()))
        self.assertEqual(other_conversation['fallback_reason'], 'request_conflict')
        followup = await self.ask('What about 5% instead?')
        self.assertEqual(followup['cards'][0]['data']['source_period']['start'], '2024-03-01')
        self.assertEqual(followup['cards'][0]['data']['potential_reduction_eur'], 15)

    async def test_expiry_restart_and_bounds_fail_without_guessing(self):
        await self.ask()
        self.service.local_state.conversations[self.conversation]['updated'] -= 1801
        expired = await self.ask('What about 10% instead?')
        self.assertEqual(expired['fallback_reason'], 'clarification_needed')
        self.service = CoachLLM()
        restarted = await self.ask('What about 10% instead?')
        self.assertEqual(restarted['fallback_reason'], 'clarification_needed')
        self.service.local_state.MAX_CONVERSATIONS = 1
        limit = await self.ask(conversation=str(uuid4()))
        self.assertEqual(limit['fallback_reason'], 'session_limit')

    async def test_local_receipt_limit_does_not_evict_retry_identity(self):
        self.service.local_state.MAX_REQUESTS = 1
        request_id = str(uuid4())
        first = await self.ask(request_id=request_id)
        result = await self.ask('What about 10% instead?')
        self.assertEqual(result['fallback_reason'], 'session_limit')
        self.assertEqual(await self.ask(request_id=request_id), first)

    async def test_existing_nonspending_topics_remain_local_and_unchanged(self):
        for question in ['Daily allowance', 'Current account balance', 'My goals', 'Mortgage']:
            baseline = answer(question, plan({}, []), [], history(self.customer, 'month'))
            result = await self.ask(question)
            self.assertEqual(result['text'], baseline['text'])
            self.assertEqual(result['kind'], baseline['kind'])
            self.assertEqual(result['fallback_reason'], 'disabled')
            self.assertEqual(result['cards'], [])


class DisabledHttpTests(unittest.TestCase):
    def test_cookie_conversation_followup_retry_and_goal_state_without_provider_or_ledger(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), \
                patch('backend.main.load_customers', return_value=[fixture(), fixture('CUST00001')]), \
                patch.object(Ledger, 'transaction', side_effect=AssertionError('No paid ledger access')):
            with TestClient(app) as client:
                base = '/api/customers/CUST04457'
                before = {key: client.get(base + '/' + key).json() for key in ('goals', 'assumptions', 'budget')}
                first_body = {'question': QUESTION, 'request_id': str(uuid4())}
                first = client.post(base + '/coach', json=first_body).json()
                self.assertEqual(first['mode'], 'rule_based')
                self.assertEqual(first['cards'][0]['data']['potential_reduction_eur'], 80)
                body = {'question': 'What about 10% instead?', 'request_id': str(uuid4()),
                        'conversation_id': first['conversation_id']}
                result = client.post(base + '/coach', json=body).json()
                self.assertEqual(result['cards'][0]['data']['potential_reduction_eur'], 40)
                self.assertEqual(client.post(base + '/coach', json=body).json(), result)
                for key, previous in before.items():
                    self.assertEqual(client.get(base + '/' + key).json(), previous)
                preview = client.post(base + '/coach', json={'question': 'preview', 'scenario': {
                    'name': 'Bike', 'amount_eur': '100', 'priority': 'flexible'}}).json()
                self.assertEqual(preview['fallback_reason'], 'goal_preview')
                self.assertIn('analysis', preview)
                client.cookies.clear()
                lost = client.post(base + '/coach', json=body).json()
                self.assertEqual(lost['fallback_reason'], 'conversation_mismatch')
                self.assertEqual(lost['cards'], [])


class BusyReadmissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger = Ledger.initialize(Path(self.directory.name) / 'usage.sqlite3', identity())
        self.started, self.release = asyncio.Event(), asyncio.Event()
        self.sent = []

        async def handler(request):
            self.sent.append(json.loads(request.content))
            self.started.set()
            await self.release.wait()
            return httpx.Response(200, json=envelope())

        self.provider = VerdaClient(Settings('dummy-qa-test-key', self.ledger, time.time() + 300),
                                    httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        self.service = CoachLLM(self.provider)
        self.addAsyncCleanup(self.provider.close)

    async def ask(self, request_id, conversation, session, question=QUESTION):
        return await self.service.respond(fixture(), question, conversation, request_id, session,
                                          {'kind': 'help', 'text': 'Local fallback', 'rows': []})

    async def test_busy_retry_after_restart_admits_once_and_preserves_conflicts_and_inflight_dedupe(self):
        first = asyncio.create_task(self.ask(str(uuid4()), str(uuid4()), 'first-browser'))
        await asyncio.wait_for(self.started.wait(), 2)
        request, conversation = str(uuid4()), str(uuid4())
        try:
            blocked = await self.ask(request, conversation, 'second-browser')
            self.assertEqual(blocked['fallback_reason'], 'concurrency_limit')
            conflict = await self.ask(request, conversation, 'second-browser', 'What about 10% instead?')
            self.assertEqual(conflict['fallback_reason'], 'request_conflict')
        finally:
            self.release.set()
            await first
        self.service = CoachLLM(self.provider)
        self.provider.settings.ledger = Ledger(self.ledger.path, identity())
        self.started.clear()
        self.release.clear()
        retry = asyncio.create_task(self.ask(request, conversation, 'second-browser'))
        try:
            await asyncio.wait_for(self.started.wait(), 2)
            duplicate = await self.ask(request, conversation, 'second-browser')
            self.assertEqual(duplicate['fallback_reason'], 'request_in_progress')
        finally:
            self.release.set()
            success = await retry
        self.assertEqual(success['mode'], 'llm')
        self.assertEqual(await self.ask(request, conversation, 'second-browser'), success)
        self.assertEqual(len(self.sent), 2)
        with self.ledger.transaction() as (db, _):
            self.assertEqual(db.execute('SELECT COUNT(*) FROM calls').fetchone()[0], 2)

    async def test_busy_receipts_with_any_call_record_are_not_reopened(self):
        busy = {'mode': 'rule_based', 'fallback_reason': 'concurrency_limit', 'cards': []}
        for suffix in (':1', ':2'):
            key = 'guard' + suffix
            self.ledger.claim(key, 'fingerprint', 'browser')
            self.ledger.finish(key, busy, 'conversation')
            self.ledger.reserve(key + suffix, INPUT_BOUND, OUTPUT_BOUND)
            if suffix == ':2':
                self.ledger.reconcile(key + suffix, {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0})
            spent = self.ledger.spent()
            self.assertEqual(self.ledger.claim(key, 'fingerprint', 'browser'), busy)
            self.assertEqual(self.ledger.spent(), spent)
        self.assertEqual(self.sent, [])

    async def test_readmission_rechecks_rate_limit_without_discarding_receipt(self):
        busy = {'mode': 'rule_based', 'fallback_reason': 'concurrency_limit', 'cards': []}
        self.ledger.claim('busy', 'fingerprint', 'browser')
        self.ledger.finish('busy', busy, 'conversation')
        with self.ledger.transaction() as (db, _):
            db.execute('UPDATE requests SET created=0 WHERE key=?', ('busy',))
        for index in range(12):
            self.ledger.claim('other-' + str(index), 'other', 'browser-' + str(index))
        with self.assertRaisesRegex(GateError, 'rate_limited'):
            self.ledger.claim('busy', 'fingerprint', 'browser')
        with self.ledger.transaction() as (db, _):
            self.assertEqual(json.loads(db.execute('SELECT response FROM requests WHERE key=?', ('busy',)).fetchone()[0]), busy)
        self.assertEqual(self.ledger.spent(), 0)


if __name__ == '__main__':
    unittest.main()
