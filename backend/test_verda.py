"""All provider traffic is mocked. No test needs a Verda API key or paid deployment."""

import asyncio
import json
import os
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from backend.coach_ledger import GateError, Ledger, cost, units
from backend.coach_llm import CoachLLM
from backend.main import Assumptions, app
from backend.test_data_coach import fixture
from backend.verda import INPUT_BOUND, OUTPUT_BOUND, MODEL, InstanceLock, Settings, VerdaClient, identity, settings_from_env

BASELINE = {'kind': 'help', 'text': 'Rule-based answer.', 'rows': []}
QUESTION = 'What if I reduce restaurants in April 2024 by 20%?'
ARGS = {'category': 'restaurants', 'period': 'month', 'period_start': '2024-04-01', 'reduction_percent': 20}


def routed(name='category_reduction', arguments=None):
    return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call_1', 'type': 'function',
             'function': {'name': name, 'arguments': json.dumps(ARGS if arguments is None else arguments)}}]}


def envelope(message, usage=True):
    result = {'model': MODEL, 'choices': [{'finish_reason': 'tool_calls' if message.get('tool_calls') else 'stop', 'message': message}]}
    if usage:
        result['usage'] = {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}
    return result


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'usage.sqlite3'
        self.config = identity()
        self.ledger = Ledger.initialize(self.path, self.config)

    def test_atomic_concurrent_reservations_near_cap_and_restart(self):
        with self.ledger.transaction() as (db, _):
            db.execute('INSERT INTO calls VALUES(?, ?, ?, ?, ?, ?)', ('prior', units('.8'), units('.8'), 1, 1, 'reserved'))
        def reserve(index):
            try:
                Ledger(self.path, self.config).reserve(str(index), INPUT_BOUND, OUTPUT_BOUND)
                return True
            except (GateError, sqlite3.OperationalError):
                return False
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(reserve, range(8)))
        self.assertEqual(sum(results), 1)
        restarted = Ledger(self.path, self.config)
        self.assertLessEqual(restarted.spent(), 1)
        with self.assertRaisesRegex(GateError, 'budget_exhausted'):
            restarted.reserve('after-restart', INPUT_BOUND, OUTPUT_BOUND)
        with self.assertRaises(FileExistsError):
            Ledger.initialize(self.path, self.config)
        with self.assertRaisesRegex(GateError, 'ledger_mismatch'):
            Ledger(self.path, {**self.config, 'cap_eur': '2.00'}).spent()

    def test_reconciliation_uncertain_usage_and_bound_violation(self):
        self.ledger.reserve('first', INPUT_BOUND, OUTPUT_BOUND)
        reserved = self.ledger.spent()
        for usage in [None, {}, {'prompt_tokens': -1}, {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 999}]:
            self.ledger.reconcile('first', usage)
            self.assertEqual(self.ledger.spent(), reserved)
        self.ledger.reconcile('first', {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120})
        self.assertEqual(self.ledger.spent(), cost(100, 20, self.config['input_rate'], self.config['output_rate']) / 10**12)
        self.ledger.reserve('second', INPUT_BOUND, OUTPUT_BOUND)
        with self.assertRaisesRegex(GateError, 'billing_uncertain'):
            self.ledger.reconcile('second', {'prompt_tokens': INPUT_BOUND + 1, 'completion_tokens': 1, 'total_tokens': INPUT_BOUND + 2})
        with self.assertRaisesRegex(GateError, 'billing_uncertain'):
            self.ledger.reserve('third', INPUT_BOUND, OUTPUT_BOUND)

    def test_missing_ledger_never_recreated_and_persistent_request_claim(self):
        self.assertIsNone(self.ledger.claim('request', 'fingerprint', 'session'))
        restarted = Ledger(self.path, self.config)
        with self.assertRaisesRegex(GateError, 'request_in_progress'):
            restarted.claim('request', 'fingerprint', 'session')
        with self.assertRaisesRegex(GateError, 'request_conflict'):
            restarted.claim('request', 'different', 'session')
        self.path.unlink()
        with self.assertRaises(sqlite3.OperationalError):
            restarted.spent()
        self.assertFalse(self.path.exists())

    def test_global_rate_limit_survives_restart(self):
        for index in range(12):
            self.assertIsNone(self.ledger.claim(f'request-{index}', 'fingerprint', f'session-{index}'))
        restarted = Ledger(self.path, self.config)
        with self.assertRaisesRegex(GateError, 'rate_limited'):
            restarted.claim('thirteenth', 'fingerprint', 'new-session')

    def test_instance_lock_and_host_bound_configuration(self):
        lock = InstanceLock(Path(self.tmp.name) / 'instance.lock')
        try:
            with self.assertRaisesRegex(GateError, 'instance_busy'):
                InstanceLock(Path(self.tmp.name) / 'instance.lock')
        finally:
            lock.close()
        InstanceLock(Path(self.tmp.name) / 'instance.lock').close()
        env = {'COACH_LLM_ENABLED': 'true', 'VERDA_MODEL': MODEL, 'VERDA_BASE_URL': 'https://inference.verda.com/v1',
               'VERDA_INFERENCE_API_KEY': 'fake-key-for-tests', 'COACH_LLM_BUDGET_EUR': '1.00'}
        directory = Path(self.tmp.name)
        review = {'identity': {**self.config, 'host': 'another-computer'}, 'single_paid_host': True, 'expires_at': time.time() + 100}
        (directory / 'approval.json').write_text(json.dumps(review), encoding='utf-8')
        with patch.dict(os.environ, env, clear=True), patch('backend.verda.state_directory', return_value=directory):
            with self.assertRaisesRegex(GateError, 'deployment_mismatch'):
                settings_from_env()
            review['identity'] = self.config
            (directory / 'approval.json').write_text(json.dumps(review), encoding='utf-8')
            settings = settings_from_env()
            settings.lock.close()
            with patch.dict(os.environ, {'VERDA_MODEL': 'unknown-deepseek'}):
                with self.assertRaisesRegex(GateError, 'unverified_model'):
                    settings_from_env()
            with patch.dict(os.environ, {'VERDA_BASE_URL': 'https://example.com/v1'}):
                with self.assertRaisesRegex(GateError, 'unapproved_endpoint'):
                    settings_from_env()
            with patch.dict(os.environ, {'COACH_LLM_BUDGET_EUR': '2.00'}):
                with self.assertRaisesRegex(GateError, 'invalid_budget'):
                    settings_from_env()
            review['expires_at'] = time.time() - 1
            (directory / 'approval.json').write_text(json.dumps(review), encoding='utf-8')
            with self.assertRaisesRegex(GateError, 'pricing_review_expired'):
                settings_from_env()
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'true', 'COACH_LLM_BUDGET_USD': '1.00'}, clear=True):
            with self.assertRaisesRegex(GateError, 'euro_budget_required'):
                settings_from_env()


class CoachLLMTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Ledger.initialize(Path(self.tmp.name) / 'usage.sqlite3', identity())
        self.queue = []
        self.requests = []
        self.release = None
        self.started = asyncio.Event()
        async def handle(request):
            self.requests.append(json.loads(request.content))
            self.started.set()
            if self.release:
                await self.release.wait()
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            if isinstance(item, httpx.Response):
                return item
            return httpx.Response(200, json=item)
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        self.provider = VerdaClient(Settings('fake-key-for-tests', self.ledger, time.time() + 1000), self.client)
        self.service = CoachLLM(self.provider)
        self.customer = fixture()
        self.conversation = str(uuid4())
        self.session = 'browser-session-one'

    async def asyncTearDown(self):
        await self.service.close()
        self.tmp.cleanup()

    async def ask(self, question=QUESTION, *, customer=None, conversation=None, session=None, request_id=None, **kwargs):
        return await self.service.respond(customer or self.customer, question, conversation or self.conversation,
                                          request_id or str(uuid4()), session or self.session, BASELINE, **kwargs)

    def valid(self, args=None):
        self.queue.append(envelope(routed(arguments=args)))

    async def test_selection_followup_and_minimal_provider_payload(self):
        self.valid()
        result = await self.ask()
        self.assertEqual(result['mode'], 'llm')
        self.assertIsNone(result['fallback_reason'])
        self.assertEqual(result['cards'][0]['data']['potential_reduction_eur'], 80)
        self.assertIn('EUR 320.00', result['text'])
        self.assertIn('not actual savings', result['text'])
        self.valid({**ARGS, 'reduction_percent': 10})
        followup = await self.ask('What about 10%?')
        self.assertEqual(followup['cards'][0]['data']['potential_reduction_eur'], 40)
        self.assertEqual(followup['cards'][0]['data']['source_period']['start'], '2024-04-01')
        payload = json.dumps(self.requests)
        for forbidden in ['CUST04457', 'bank_account_id', 'customer_id', 'goal_id', 'classifications', 'merchant', 'fake-key-for-tests']:
            self.assertNotIn(forbidden, payload)
        for request in self.requests:
            self.assertEqual(request['reasoning_effort'], 'none')
            self.assertEqual(request['max_tokens'], OUTPUT_BOUND)
        self.assertEqual(len(self.requests), 2)

    async def test_category_and_comparison_tools(self):
        for question, name, args, expected in [
            ('Restaurants spending in April 2024', 'category_spending', {k: v for k, v in ARGS.items() if k != 'reduction_percent'}, 400),
            ('Compare monthly spending', 'spending_comparison', {'period': 'month'}, 200),
        ]:
            self.queue.append(envelope(routed(name, args)))
            result = await self.ask(question)
            self.assertEqual(result['mode'], 'llm')
            data = result['cards'][0]['data']
            self.assertEqual(data['spending_eur'] if name == 'category_spending' else data['difference_eur'], expected)

    async def test_session_customer_isolation_and_no_cross_customer_followup(self):
        self.valid()
        await self.ask()
        before = len(self.requests)
        for kwargs in [{'session': 'other-browser'}, {'customer': fixture('CUST00001')}]:
            result = await self.ask('What about 10%?', **kwargs)
            self.assertEqual(result['fallback_reason'], 'conversation_mismatch')
        self.assertEqual(len(self.requests), before)
        result = await self.ask('What about 10%?', customer=fixture('CUST00001'), conversation=str(uuid4()))
        self.assertEqual(result['fallback_reason'], 'clarification_needed')
        self.assertEqual(result['cards'], [])
        self.assertEqual(len(self.requests), before)

    async def test_privacy_blocking_and_context_expiry(self):
        for question in ['My IBAN is FI2112345600000785', 'Email me at a@example.com', 'My name is Alice Smith',
                         'api key sk-abcdef', 'CUST04457 restaurants', 'Salary 3000 EUR', 'https://example.com', 'line one\nline two']:
            result = await self.ask(question)
            self.assertEqual(result['fallback_reason'], 'privacy_blocked')
        self.assertEqual(self.requests, [])
        self.valid()
        await self.ask()
        with self.ledger.transaction() as (db, _):
            db.execute('UPDATE conversations SET updated=?', (time.time() - 1801,))
        before, spent = len(self.requests), self.ledger.spent()
        result = await self.ask('What about 10%?')
        self.assertEqual(result['fallback_reason'], 'clarification_needed')
        self.assertEqual(len(self.requests), before)
        self.assertEqual(self.ledger.spent(), spent)

    async def test_invalid_tools_arguments_and_ungrounded_periods(self):
        for index, message in enumerate([
            routed('write_goal'), routed(arguments={**ARGS, 'url': 'https://example.com'}),
            routed(arguments={**ARGS, 'reduction_percent': 101}), routed(arguments={**ARGS, 'period_start': '2024-03-01'}),
        ]):
            self.queue.append(envelope(message))
            result = await self.ask(session='validation-' + str(index), conversation=str(uuid4()))
            self.assertEqual(result['mode'], 'rule_based')
            self.assertEqual(result['cards'], [])
        self.assertEqual(len(self.requests), 4)

    async def test_untrusted_model_prose_is_rejected_without_explanation_call(self):
        self.queue.append(envelope({**routed(), 'content': 'You saved EUR 999999'}))
        result = await self.ask()
        self.assertEqual(result['fallback_reason'], 'invalid_model_output')
        self.assertEqual(result['mode'], 'rule_based')
        self.assertEqual(result['cards'], [])
        self.assertNotIn('999999', result['text'])
        self.assertEqual(len(self.requests), 1)
        self.valid()
        successful = await self.ask()
        self.assertEqual(successful['mode'], 'llm')
        self.assertEqual(successful['cards'][0]['data']['potential_reduction_eur'], 80)
        self.assertIn('not actual savings', successful['text'])
        self.assertEqual(len(self.requests), 2)

    async def test_provider_errors_retain_reservation_no_retries(self):
        self.queue.append(httpx.Response(401, json={'secret': 'never-return-this-provider-body'}))
        result = await self.ask()
        self.assertEqual(result['fallback_reason'], 'provider_error')
        self.assertEqual(result['cards'][0]['data']['potential_reduction_eur'], 80)
        self.assertIn('not actual savings', result['text'])
        self.assertNotIn('never-return', json.dumps(result))
        self.assertEqual(len(self.requests), 1)
        self.assertGreater(self.ledger.spent(), 0.14)
        self.queue.append(envelope(routed(), usage=False))
        result = await self.ask()
        self.assertEqual(result['mode'], 'llm')
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.ledger.spent(), 0.2804532224)

    async def test_missing_usage_restart_reserves_budget_and_wrong_model_freezes(self):
        self.queue.append(envelope(routed(), usage=False))
        result = await self.ask()
        self.assertEqual(result['mode'], 'llm')
        reserved = self.ledger.spent()
        restarted = Ledger(self.ledger.path, self.ledger.identity)
        self.assertEqual(restarted.spent(), reserved)
        wrong_model = envelope(routed())
        wrong_model['model'] = 'unpriced-model'
        self.queue.append(wrong_model)
        result = await self.ask()
        self.assertEqual(result['fallback_reason'], 'billing_uncertain')
        before = len(self.requests)
        result = await self.ask()
        self.assertEqual(result['fallback_reason'], 'billing_uncertain')
        self.assertEqual(len(self.requests), before)

    async def test_first_call_timeout_preserves_reservation_without_retry(self):
        self.queue.append(httpx.ReadTimeout('simulated timeout'))
        result = await self.ask()
        self.assertEqual(result['mode'], 'rule_based')
        self.assertEqual(result['fallback_reason'], 'timeout')
        self.assertEqual(result['cards'][0]['data']['potential_reduction_eur'], 80)
        self.assertIn('not actual savings', result['text'])
        self.assertEqual(len(self.requests), 1)
        self.assertGreater(self.ledger.spent(), 0.14)

    async def test_total_deadline_duplicate_inflight_and_global_concurrency(self):
        self.release = asyncio.Event()
        self.valid()
        request_id = str(uuid4())
        first = asyncio.create_task(self.ask(request_id=request_id))
        await self.started.wait()
        duplicate = await self.ask(request_id=request_id)
        self.assertEqual(duplicate['fallback_reason'], 'request_in_progress')
        other = await self.ask(conversation=str(uuid4()), session='other-browser')
        self.assertEqual(other['fallback_reason'], 'concurrency_limit')
        self.release.set()
        self.assertEqual((await first)['mode'], 'llm')
        self.release = asyncio.Event()
        self.service.deadline_seconds = .03
        start = time.monotonic()
        result = await self.ask()
        self.assertEqual(result['fallback_reason'], 'timeout')
        self.assertLess(time.monotonic() - start, .5)
        # Slow local preparation may exhaust the deadline before the provider starts.
        self.assertIn(len(self.requests), (1, 2))

    async def test_completed_duplicates_restart_and_conflict(self):
        self.valid()
        request_id = str(uuid4())
        result = await self.ask(request_id=request_id)
        spent = self.ledger.spent()
        self.service = CoachLLM(self.provider)
        duplicate = await self.ask(request_id=request_id)
        self.assertEqual(result, duplicate)
        self.assertEqual(self.ledger.spent(), spent)
        self.assertEqual(len(self.requests), 1)
        conflicting = await self.ask('What about 10%?', request_id=request_id)
        self.assertEqual(conflicting['fallback_reason'], 'request_conflict')
        self.assertEqual(len(self.requests), 1)

    async def test_budget_exhaustion_rate_limit_and_disabled_fallback(self):
        with self.ledger.transaction() as (db, _):
            db.execute('INSERT INTO calls VALUES(?, ?, ?, ?, ?, ?)', ('exhausted', units(1), units(1), 1, 1, 'reserved'))
        for _ in range(4):
            result = await self.ask()
            self.assertEqual(result['fallback_reason'], 'budget_exhausted')
            self.assertEqual(result['mode'], 'rule_based')
            self.assertEqual(result['cards'][0]['data']['potential_reduction_eur'], 80)
        result = await self.ask()
        self.assertEqual(result['fallback_reason'], 'rate_limited')
        self.assertEqual(self.requests, [])
        disabled = CoachLLM()
        result = await disabled.respond(self.customer, 'current account balance', self.conversation, str(uuid4()), self.session, BASELINE)
        self.assertEqual(result['text'], BASELINE['text'])
        self.assertEqual(result['fallback_reason'], 'disabled')


class CoachRouteTests(unittest.TestCase):
    def test_enabled_http_route_bootstrap_followup_and_nonmutation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger.initialize(Path(directory) / 'usage.sqlite3', identity())
            sent = []
            queue = [envelope(routed()), envelope(routed(arguments={**ARGS, 'reduction_percent': 10}))]
            async def handler(request):
                sent.append(json.loads(request.content))
                return httpx.Response(200, json=queue.pop(0))
            provider = VerdaClient(Settings('mock-key', ledger, time.time() + 1000),
                                   httpx.AsyncClient(transport=httpx.MockTransport(handler)))
            with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), patch('backend.main.load_customers',
                                                                            return_value=[fixture(), fixture('CUST00001')]):
                with TestClient(app) as client:
                    app.state.coach_llm = CoachLLM(provider)
                    base = '/api/customers/CUST04457'
                    inputs = {name: '100.00' for name in ['available_funds_eur', 'confirmed_income_eur',
                              'upcoming_essential_bills_eur', 'emergency_reserve_eur', 'everyday_spending_eur',
                              'voluntary_goal_contribution_eur']}
                    client.put(base + '/assumptions', json=inputs).raise_for_status()
                    client.post(base + '/goals', json={'name': 'Private goal name', 'amount_eur': '10', 'priority': 'critical'})
                    before = {name: client.get(base + '/' + name).json() for name in ['goals', 'assumptions', 'budget']}
                    boot = client.post(base + '/coach', json={'question': QUESTION}).json()
                    self.assertEqual(boot['fallback_reason'], 'session_initialized')
                    self.assertEqual(sent, [])
                    allowance = client.post(base + '/coach', json={'question': 'Daily allowance'}).json()
                    self.assertEqual(allowance['kind'], 'allowance')
                    self.assertEqual(allowance['fallback_reason'], 'unsupported_topic')
                    self.assertEqual(sent, [])
                    untracked = client.post(base + '/coach', json={'question': QUESTION}).json()
                    self.assertEqual(untracked['fallback_reason'], 'conversation_required')
                    self.assertEqual(sent, [])
                    request = {'question': QUESTION, 'conversation_id': boot['conversation_id'], 'request_id': str(uuid4())}
                    first = client.post(base + '/coach', json=request).json()
                    self.assertEqual(first['mode'], 'llm')
                    self.assertEqual(client.post(base + '/coach', json=request).json(), first)
                    self.assertEqual(len(sent), 1)
                    followup = client.post(base + '/coach', json={**request, 'request_id': str(uuid4()),
                                                                'question': 'What about 10%?'}).json()
                    self.assertEqual(followup['cards'][0]['data']['potential_reduction_eur'], 40)
                    other = client.post('/api/customers/CUST00001/coach', json={**request, 'request_id': str(uuid4())}).json()
                    self.assertEqual(other['fallback_reason'], 'conversation_mismatch')
                    self.assertEqual(len(sent), 2)
                    self.assertNotIn('Private goal name', json.dumps(sent))
                    for name, value in before.items():
                        self.assertEqual(client.get(base + '/' + name).json(), value)

    def test_additive_fields_cookies_and_legacy_scenario_without_paid_configuration(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), patch('backend.main.load_customers', return_value=[fixture()]):
            with TestClient(app) as client:
                base = '/api/customers/CUST04457'
                response = client.post(base + '/coach', json={'question': 'spending categories'})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data['mode'], 'rule_based')
                self.assertEqual(data['fallback_reason'], 'disabled')
                self.assertIn('HttpOnly', response.headers['set-cookie'])
                self.assertIn('SameSite=strict', response.headers['set-cookie'])
                self.assertTrue(data['conversation_id'])
                self.assertTrue(data['request_id'])
                self.assertIn('rows', data)
                scenario = {'name': 'Bike', 'amount_eur': '100', 'priority': 'flexible'}
                preview = client.post(base + '/coach', json={'question': 'preview', 'scenario': scenario}).json()
                self.assertEqual(preview['preview'], scenario)
                self.assertIn('analysis', preview)
                self.assertIn('baseline', preview)
                self.assertEqual(preview['fallback_reason'], 'goal_preview')
                invalid = client.post(base + '/coach', json={'question': 'hello', 'conversation_id': 'not-a-uuid'})
                self.assertEqual(invalid.status_code, 422)


if __name__ == '__main__':
    unittest.main()
