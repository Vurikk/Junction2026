"""Browser HTTP boundary regressions; synthetic customers, mock transport and disposable ledger."""

from contextlib import contextmanager
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

from backend.coach_ledger import Ledger
from backend.coach_llm import CoachLLM
from backend.main import app
from backend.test_data_coach import fixture
from backend.verda import MODEL, Settings, VerdaClient, identity


QUESTION = 'Reduce restaurants in April 2024 by 20%'
BASE = '/api/customers/CUST04457/coach'


def model_response():
    args = {'category': 'restaurants', 'period': 'month', 'period_start': '2024-04-01', 'reduction_percent': 20}
    return httpx.Response(200, json={
        'model': MODEL,
        'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120},
        'choices': [{'finish_reason': 'tool_calls', 'message': {'content': None, 'tool_calls': [
            {'type': 'function', 'function': {'name': 'category_reduction', 'arguments': json.dumps(args)}},
        ]}}],
    })


class BrowserContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger = Ledger.initialize(Path(self.directory.name) / 'usage.sqlite3', identity())
        self.sent = []
        self.queue = []

        async def handler(request):
            self.sent.append(json.loads(request.content))
            return self.queue.pop(0)

        self.provider = VerdaClient(Settings('dummy-browser-test-key', self.ledger, time.time() + 300),
                                    httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        self.service = CoachLLM(self.provider)

    @contextmanager
    def browser(self):
        with patch.dict(os.environ, {'COACH_LLM_ENABLED': 'false'}), \
                patch('backend.main.load_customers', return_value=[fixture(), fixture('CUST00001')]), \
                patch('backend.coach_llm.CoachLLM.from_env', return_value=self.service):
            with TestClient(app, base_url='https://testserver') as client:
                yield client

    def bootstrap(self, client):
        response = client.post(BASE, json={'question': 'Spending by category', 'request_id': str(uuid4())})
        self.assertEqual(response.status_code, 200)
        return response

    def test_https_cookie_and_existing_cookie_bootstrap_never_claim_paid_work(self):
        with self.browser() as client:
            first = self.bootstrap(client)
            cookie = first.headers['set-cookie']
            for attribute in ('HttpOnly', 'Secure', 'SameSite=strict', 'Path=/api', 'Max-Age=3600'):
                self.assertIn(attribute, cookie)
            self.assertEqual(first.json()['fallback_reason'], 'session_initialized')
            second = self.bootstrap(client)
            self.assertEqual(second.json()['fallback_reason'], 'conversation_required')
            self.assertNotEqual(first.json()['conversation_id'], second.json()['conversation_id'])
            self.assertEqual(self.sent, [])
            with self.ledger.transaction() as (db, _):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM calls').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)
            self.assertEqual(self.ledger.spent(), 0)

    def test_cookie_loss_after_completed_turn_does_not_reissue_model_call(self):
        self.queue.append(model_response())
        with self.browser() as client:
            conversation = self.bootstrap(client).json()['conversation_id']
            body = {'question': QUESTION, 'conversation_id': conversation, 'request_id': str(uuid4())}
            success = client.post(BASE, json=body).json()
            self.assertEqual(success['mode'], 'llm')
            self.assertEqual(len(self.sent), 1)
            cost_before = self.ledger.spent()
            client.cookies.clear()
            recovery = client.post(BASE, json=body).json()
            self.assertEqual(recovery['fallback_reason'], 'session_initialized')
            self.assertEqual(recovery['conversation_id'], conversation)
            repeated = client.post(BASE, json=body).json()
            self.assertEqual(repeated['fallback_reason'], 'conversation_mismatch')
            self.assertEqual(repeated['cards'], [])
            self.assertEqual(len(self.sent), 1)
            self.assertEqual(self.ledger.spent(), cost_before)

    def test_provider_failure_replay_after_service_restart_keeps_card_and_reservation(self):
        self.queue.append(httpx.Response(503, json={'detail': 'private-provider-body'}))
        with self.browser() as client:
            conversation = self.bootstrap(client).json()['conversation_id']
            body = {'question': QUESTION, 'conversation_id': conversation, 'request_id': str(uuid4())}
            failed = client.post(BASE, json=body).json()
            self.assertEqual(failed['mode'], 'rule_based')
            self.assertEqual(failed['fallback_reason'], 'provider_error')
            self.assertEqual(failed['cards'][0]['data']['potential_reduction_eur'], 80)
            self.assertNotIn('private-provider-body', json.dumps(failed))
            reserved = self.ledger.spent()
            self.assertEqual(reserved, 0.1402266112)
            self.provider.settings.ledger = Ledger(self.ledger.path, identity())
            app.state.coach_llm = CoachLLM(self.provider)
            replay = client.post(BASE, json=body).json()
            self.assertEqual(replay, failed)
            self.assertEqual(len(self.sent), 1)
            self.assertEqual(self.ledger.spent(), reserved)


if __name__ == '__main__':
    unittest.main()
