"""Single-call regression tests: mocked HTTP only, synthetic data and temporary EUR ledgers."""

import asyncio
from copy import deepcopy
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

from backend.coach_ledger import Ledger, cost, units
from backend.coach_llm import CoachLLM
from backend.main import app
from backend.test_data_coach import fixture
from backend.verda import INPUT_BOUND, MODEL, OUTPUT_BOUND, Settings, VerdaClient, identity

BASELINE = {'kind': 'help', 'text': 'Rule-based answer.', 'rows': []}
QUESTION = 'What if I reduce restaurants in April 2024 by 20%?'
ARGS = {'category': 'restaurants', 'period': 'month', 'period_start': '2024-04-01', 'reduction_percent': 20}
COVERAGE = 'Recorded coverage may be incomplete. Transfers and refunds are excluded.'
HYPOTHETICAL = 'This is not actual savings. Goals and confirmed inputs are unchanged; goal impact is unknown.'


def routed(name='category_reduction', arguments=None):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'call_1', 'type': 'function', 'function': {
            'name': name, 'arguments': json.dumps(ARGS if arguments is None else arguments),
        }},
    ]}


def envelope(message=None, usage=True):
    result = {'model': MODEL, 'choices': [{'finish_reason': 'tool_calls', 'message': message or routed()}]}
    if usage:
        result['usage'] = {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}
    return result


class SingleCallTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Ledger.initialize(Path(self.tmp.name) / 'usage.sqlite3', identity())
        self.requests = []
        self.queue = []
        self.started = asyncio.Event()
        self.release = None

        async def handle(request):
            self.requests.append(json.loads(request.content))
            self.started.set()
            if self.release is not None:
                await self.release.wait()
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item if isinstance(item, httpx.Response) else httpx.Response(200, json=item)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        self.provider = VerdaClient(Settings('fake-key-for-tests', self.ledger, time.time() + 1000), client)
        self.service = CoachLLM(self.provider)
        self.addAsyncCleanup(self.service.close)
        self.customer = fixture()
        self.conversation = str(uuid4())
        self.session = 'single-call-browser'

    async def ask(self, question=QUESTION, *, request_id=None, customer=None, conversation=None, session=None):
        return await self.service.respond(customer or self.customer, question, conversation or self.conversation,
                                          request_id, session or self.session, BASELINE)

    def calls(self):
        with self.ledger.transaction() as (db, _):
            return db.execute('SELECT key, reserved, charged, state FROM calls ORDER BY key').fetchall()

    async def test_reduction_exact_card_explanation_and_one_reservation(self):
        self.queue.append(envelope())
        with patch.object(self.ledger, 'reserve', wraps=self.ledger.reserve) as reserve:
            result = await self.ask()
        reserve.assert_called_once()
        self.assertTrue(reserve.call_args.args[0].endswith(':1'))
        self.assertEqual(reserve.call_args.args[1:], (INPUT_BOUND, OUTPUT_BOUND))
        self.assertEqual(result['mode'], 'llm')
        self.assertIsNone(result['fallback_reason'])
        self.assertEqual(result['kind'], 'scenario')
        self.assertEqual(result['rows'], [])
        self.assertEqual(result['conversation_id'], self.conversation)
        self.assertTrue(result['request_id'])
        self.assertEqual(result['cards'], [{'type': 'category_reduction', 'data': {
            'currency': 'EUR', 'category': 'restaurants', 'period': 'month',
            'source_period': {'start': '2024-04-01', 'end': '2024-04-30'}, 'reduction_percent': 20,
            'baseline_spending_eur': 400, 'hypothetical_spending_eur': 320, 'potential_reduction_eur': 80,
        }}])
        self.assertEqual(result['text'], 'restaurants (2024-04-01 to 2024-04-30): EUR 400.00 recorded; '
                         'at 20% reduction, EUR 320.00 hypothetical; EUR 80.00 potential spending reduction. '
                         + COVERAGE + ' ' + HYPOTHETICAL)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(len(self.calls()), 1)
        expected = cost(100, 20, self.ledger.identity['input_rate'], self.ledger.identity['output_rate'])
        self.assertEqual(self.calls()[0][2:], (expected, 'reconciled'))
        self.assertIn('tools', self.requests[0])
        self.assertEqual(self.requests[0]['max_tokens'], OUTPUT_BOUND)
        payload = json.dumps(self.requests)
        for forbidden in ['fact_ids', 'hypothetical_spending_eur', 'CUST04457', 'customer_id', 'bank_account_id',
                          'merchant', 'fake-key-for-tests']:
            self.assertNotIn(forbidden, payload)

    async def test_category_and_comparison_each_use_one_call(self):
        cases = [
            ('Restaurants spending in April 2024', 'category_spending',
             {key: value for key, value in ARGS.items() if key != 'reduction_percent'}, 'categories',
             'restaurants (2024-04-01 to 2024-04-30): EUR 400.00 recorded spending.'),
            ('Compare monthly spending', 'spending_comparison', {'period': 'month'}, 'average',
             '2024-04-01 to 2024-04-30: EUR 400.00 recorded spending; prior-period average EUR 200.00; above average.'),
        ]
        for question, name, arguments, kind, summary in cases:
            with self.subTest(tool=name):
                before = len(self.requests)
                self.queue.append(envelope(routed(name, arguments)))
                result = await self.ask(question)
                self.assertEqual(result['mode'], 'llm')
                self.assertIsNone(result['fallback_reason'])
                self.assertEqual(result['kind'], kind)
                self.assertEqual(result['text'], summary + ' ' + COVERAGE)
                data = result['cards'][0]['data']
                if name == 'category_spending':
                    self.assertEqual(data['spending_eur'], 400)
                else:
                    self.assertEqual(data['comparison']['spending_eur'], 400)
                    self.assertEqual(data['baseline']['average_spending_eur'], 200)
                    self.assertEqual(data['difference_eur'], 200)
                    self.assertFalse(data['coverage']['completeness_guaranteed'])
                self.assertEqual(len(self.requests), before + 1)
                self.assertEqual(len(self.calls()), before + 1)

    async def test_insufficient_history_remains_honest(self):
        customer = fixture(records=[('2024-04-10', 'purchase', -10, 'Restaurants', 'one', 10),
                                    ('2024-05-10', 'transfer', 0, 'transfer', 'one', 10)])
        self.queue.append(envelope(routed('spending_comparison', {'period': 'month'})))
        result = await self.ask('Compare monthly spending', customer=customer)
        self.assertEqual(result['mode'], 'llm')
        self.assertEqual(result['cards'][0]['data']['status'], 'insufficient_data')
        self.assertIsNone(result['cards'][0]['data']['baseline'])
        self.assertEqual(result['text'], 'There is insufficient full-period history for a comparison. ' + COVERAGE)
        self.assertEqual(len(self.requests), 1)

    async def test_followup_context_survives_service_and_ledger_restart(self):
        self.queue.append(envelope())
        await self.ask()
        self.provider.settings.ledger = Ledger(self.ledger.path, self.ledger.identity)
        self.service = CoachLLM(self.provider)
        self.queue.append(envelope(routed(arguments={**ARGS, 'reduction_percent': 10})))
        result = await self.ask('What about 10%?')
        previous = json.loads(self.requests[1]['messages'][1]['content'])['context']['previous_selection']
        self.assertEqual(previous['name'], 'category_reduction')
        self.assertEqual(previous['arguments']['category'], 'restaurants')
        self.assertEqual(previous['arguments']['period_start'], '2024-04-01')
        self.assertEqual(result['mode'], 'llm')
        data = result['cards'][0]['data']
        self.assertEqual(data['baseline_spending_eur'], 400)
        self.assertEqual(data['hypothetical_spending_eur'], 360)
        self.assertEqual(data['potential_reduction_eur'], 40)
        self.assertIn(HYPOTHETICAL, result['text'])
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(len(self.calls()), 2)

    async def test_customer_browser_isolation_and_context_expiry(self):
        self.queue.append(envelope())
        await self.ask()
        for scope in [{'session': 'other-browser'}, {'customer': fixture('CUST00001')}]:
            result = await self.ask('What about 10%?', **scope)
            self.assertEqual(result['fallback_reason'], 'conversation_mismatch')
            self.assertEqual(result['mode'], 'rule_based')
            self.assertEqual(result['cards'], [])
        self.assertEqual(len(self.requests), 1)
        with self.ledger.transaction() as (db, _):
            db.execute('UPDATE conversations SET updated=?', (time.time() - 1801,))
        spent = self.ledger.spent()
        expired = await self.ask('What about 10%?')
        self.assertEqual(expired['fallback_reason'], 'clarification_needed')
        self.assertEqual(expired['cards'], [])
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.ledger.spent(), spent)

    async def test_cached_duplicates_explicit_and_derived_ids_do_not_pay_after_restart(self):
        for request_id in (str(uuid4()), None):
            with self.subTest(request_id=request_id):
                self.conversation = str(uuid4())
                self.queue.append(envelope())
                result = await self.ask(request_id=request_id)
                before, spent = len(self.requests), self.ledger.spent()
                self.provider.settings.ledger = Ledger(self.ledger.path, self.ledger.identity)
                self.service = CoachLLM(self.provider)
                self.assertEqual(await self.ask(request_id=request_id), result)
                self.assertEqual(len(self.requests), before)
                self.assertEqual(self.ledger.spent(), spent)
                if request_id:
                    conflict = await self.ask('What about 10%?', request_id=request_id)
                    self.assertEqual(conflict['fallback_reason'], 'request_conflict')
                    self.assertEqual(len(self.requests), before)

    async def test_inflight_duplicate_and_concurrency_do_not_add_calls(self):
        self.queue.append(envelope())
        self.release = asyncio.Event()
        request_id = str(uuid4())
        first = asyncio.create_task(self.ask(request_id=request_id))
        try:
            await asyncio.wait_for(self.started.wait(), timeout=2)
            duplicate = await self.ask(request_id=request_id)
            self.assertEqual(duplicate['fallback_reason'], 'request_in_progress')
            other = await self.ask(conversation=str(uuid4()), session='other-browser')
            self.assertEqual(other['fallback_reason'], 'concurrency_limit')
        finally:
            self.release.set()
            result = await first
        self.assertEqual(result['mode'], 'llm')
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(len(self.calls()), 1)

    async def test_missing_usage_reserves_only_one_call_and_budget_survives_restart(self):
        # Only one worst-case reservation fits; a redundant second call would exhaust the cap.
        with self.ledger.transaction() as (db, _):
            db.execute('INSERT INTO calls VALUES(?, ?, ?, ?, ?, ?)', ('prior', units('.8'), units('.8'), 1, 1, 'reserved'))
        self.queue.append(envelope(usage=False))
        result = await self.ask()
        self.assertEqual(result['mode'], 'llm')
        self.assertIsNone(result['fallback_reason'])
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(len(self.calls()), 2)  # Existing charge plus exactly one new reservation.
        self.assertTrue(all(not row[0].endswith(':2') for row in self.calls()))
        self.assertEqual(self.ledger.spent(), 0.9402266112)
        self.provider.settings.ledger = Ledger(self.ledger.path, self.ledger.identity)
        self.service = CoachLLM(self.provider)
        result = await self.ask(request_id=str(uuid4()))
        self.assertEqual(result['fallback_reason'], 'budget_exhausted')
        self.assertEqual(result['mode'], 'rule_based')
        self.assertEqual(result['cards'][0]['data']['potential_reduction_eur'], 80)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.ledger.spent(), 0.9402266112)

    async def test_provider_errors_fall_back_without_retry_and_keep_reservations(self):
        for item, reason in [(httpx.Response(401, json={'secret': 'private-provider-body'}), 'provider_error'),
                             (httpx.ReadTimeout('private-provider-timeout'), 'timeout')]:
            with self.subTest(reason=reason):
                before = len(self.requests)
                self.queue.append(item)
                result = await self.ask(request_id=str(uuid4()))
                self.assertEqual(result['mode'], 'rule_based')
                self.assertEqual(result['fallback_reason'], reason)
                self.assertEqual(result['cards'][0]['data']['potential_reduction_eur'], 80)
                self.assertIn(HYPOTHETICAL, result['text'])
                self.assertNotIn('private-provider', json.dumps(result))
                self.assertEqual(len(self.requests), before + 1)
                self.assertEqual(len(self.calls()), before + 1)
        self.assertEqual(self.ledger.spent(), 0.2804532224)

    async def test_validation_errors_do_not_expose_model_prose_or_add_calls(self):
        for message, reason in [
            (routed('write_goal'), 'invalid_model_output'),
            (routed(arguments={**ARGS, 'reduction_percent': 101}), 'invalid_model_output'),
            (routed(arguments={**ARGS, 'period_start': '2024-03-01'}), 'clarification_needed'),
            ({**routed(), 'content': 'You saved EUR 999999.'}, 'invalid_model_output'),
        ]:
            with self.subTest(message=message):
                before = len(self.requests)
                self.queue.append(envelope(message))
                result = await self.ask(request_id=str(uuid4()))
                self.assertEqual(result['mode'], 'rule_based')
                self.assertEqual(result['fallback_reason'], reason)
                self.assertEqual(result['cards'], [])
                self.assertNotIn('999999', result['text'])
                self.assertEqual(len(self.requests), before + 1)
                self.assertEqual(len(self.calls()), before + 1)

    async def test_failed_calculation_is_not_reported_as_llm_success(self):
        result = await self.ask('What if I reduce restaurants in May 2024 by 20%?')
        self.assertEqual(result['mode'], 'rule_based')
        self.assertEqual(result['fallback_reason'], 'unsupported_period_or_category')
        self.assertEqual(result['cards'], [])
        self.assertEqual(self.requests, [])
        self.assertEqual(self.calls(), [])

    async def test_disabled_configuration_keeps_rule_based_response(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}):
            disabled = CoachLLM.from_env()
        result = await disabled.respond(self.customer, QUESTION, self.conversation, str(uuid4()), self.session, BASELINE)
        self.assertEqual(result['mode'], 'rule_based')
        self.assertEqual(result['fallback_reason'], 'disabled')
        self.assertEqual(result['text'], BASELINE['text'])
        self.assertEqual(result['cards'], [])
        self.assertEqual(self.requests, [])
        self.assertEqual(self.calls(), [])


class SingleCallApiTests(unittest.TestCase):
    def test_goal_preview_contract_with_mock_provider_remains_local_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger.initialize(Path(directory) / 'usage.sqlite3', identity())
            sent = []

            def handle(request):
                sent.append(json.loads(request.content))
                return httpx.Response(500)

            provider = VerdaClient(Settings('fake-key-for-tests', ledger, time.time() + 1000),
                                   httpx.AsyncClient(transport=httpx.MockTransport(handle)))
            with patch('backend.main.load_customers', return_value=[fixture()]), \
                    patch('backend.coach_llm.CoachLLM.from_env', return_value=CoachLLM(provider)):
                with TestClient(app) as client:
                    base = '/api/customers/CUST04457'
                    before = {key: deepcopy(client.get(base + '/' + key).json()) for key in ['goals', 'assumptions', 'budget']}
                    scenario = {'name': 'Bike', 'amount_eur': '100', 'priority': 'flexible'}
                    response = client.post(base + '/coach', json={'question': 'preview', 'scenario': scenario})
                    self.assertEqual(response.status_code, 200)
                    preview = response.json()
                    self.assertEqual(preview['preview'], scenario)
                    self.assertIn('analysis', preview)
                    self.assertIn('baseline', preview)
                    self.assertIn('text', preview)
                    self.assertIn('rows', preview)
                    self.assertEqual(preview['mode'], 'rule_based')
                    self.assertEqual(preview['fallback_reason'], 'goal_preview')
                    self.assertEqual(preview['cards'], [])
                    self.assertTrue(preview['conversation_id'])
                    self.assertTrue(preview['request_id'])
                    for key, expected in before.items():
                        self.assertEqual(client.get(base + '/' + key).json(), expected)
                    self.assertEqual(sent, [])
                    self.assertEqual(ledger.spent(), 0)


if __name__ == '__main__':
    unittest.main()
