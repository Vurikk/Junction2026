"""Orchestration routing regressions; no provider or customer data access."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from backend.coach import answer
from backend.coach_llm import CoachLLM
from backend.coach_ledger import GateError
from backend.financial import history, plan
from backend.test_data_coach import fixture


def call(name, arguments):
    return {'content': None, 'tool_calls': [{'type': 'function', 'function': {
        'name': name, 'arguments': json.dumps(arguments),
    }}]}


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.customer = fixture()
        self.ledger = Mock()
        self.ledger.conversation.return_value = None
        self.ledger.claim.return_value = None
        self.provider = SimpleNamespace(settings=SimpleNamespace(ledger=self.ledger), complete=AsyncMock())
        self.service = CoachLLM(self.provider)

    async def ask(self, question):
        baseline = answer(question, plan({}, []), [], history(self.customer, 'month'))
        return await self.service.respond(self.customer, question, str(uuid4()), str(uuid4()), 'browser', baseline)

    async def test_weekly_spending_and_reduction_bypass_legacy_allowance_keyword(self):
        args = {'category': 'restaurants', 'period': 'week', 'period_start': '2024-04-15'}
        self.provider.complete.side_effect = [call('category_spending', args),
                                             call('category_reduction', {**args, 'reduction_percent': 20})]
        for question, expected in [('Show restaurants spending for week 2024-04-15', 'category_spending'),
                                   ('Reduce weekly restaurants spending for 2024-04-15 by 20%', 'category_reduction')]:
            with self.subTest(question=question):
                result = await self.ask(question)
                self.assertEqual(result['mode'], 'llm')
                self.assertEqual(result['cards'][0]['type'], expected)
        self.assertEqual(self.provider.complete.await_count, 2)

    async def test_real_allowance_remains_local(self):
        result = await self.ask('What is my weekly allowance?')
        self.assertEqual(result['kind'], 'allowance')
        self.assertEqual(result['fallback_reason'], 'unsupported_topic')
        self.provider.complete.assert_not_awaited()

    async def test_more_than_usual_is_comparison_not_an_increase_request(self):
        self.provider.complete.return_value = call('spending_comparison', {'period': 'month'})
        result = await self.ask('Am I spending more than usual?')
        self.assertEqual(result['mode'], 'llm')
        self.assertEqual(result['cards'][0]['type'], 'spending_comparison')
        self.assertEqual(result['cards'][0]['data']['difference_eur'], 200)

    async def test_weekly_provider_failure_keeps_calculated_card_not_allowance(self):
        self.provider.complete.side_effect = GateError('provider_error')
        result = await self.ask('Reduce weekly restaurants spending for 2024-04-15 by 20%')
        self.assertEqual(result['mode'], 'rule_based')
        self.assertEqual(result['fallback_reason'], 'provider_error')
        self.assertEqual(result['kind'], 'scenario')
        self.assertEqual(result['cards'][0]['data']['potential_reduction_eur'], 80)
        self.assertIn('2024-04-15', result['text'])
        self.assertNotIn('Confirm on Home', result['text'])
        self.provider.complete.assert_awaited_once()

    async def test_food_and_missing_period_clarify_before_any_paid_request(self):
        cases = [('Could I spend less on food?', 'groceries or restaurants'),
                 ('Reduce restaurants spending by 20%', 'Which recorded month or week')]
        for question, text in cases:
            result = await self.ask(question)
            self.assertEqual(result['fallback_reason'], 'clarification_needed')
            self.assertIn(text, result['text'])
            self.assertEqual(result['cards'], [])
        self.provider.complete.assert_not_awaited()

    async def test_unsupported_period_is_local_and_never_substituted(self):
        result = await self.ask('Restaurants spending in January 2030')
        self.assertEqual(result['fallback_reason'], 'unsupported_period_or_category')
        self.assertEqual(result['cards'], [])
        self.provider.complete.assert_not_awaited()

    async def test_latest_recorded_week_without_category_does_not_become_allowance(self):
        result = await self.ask('What if I reduce restaurants in latest recorded week by 20%?')
        self.assertEqual(result['fallback_reason'], 'unsupported_period_or_category')
        self.assertEqual(result['kind'], 'help')
        self.assertNotIn('Confirm on Home', result['text'])
        self.provider.complete.assert_not_awaited()

    async def test_overall_breakdown_and_followup_preserve_validated_selection(self):
        args = {'category': 'all', 'period': 'month', 'period_start': '2024-04-01'}
        self.provider.complete.return_value = call('category_spending', args)
        result = await self.ask('Where does most of my money go?')
        self.assertEqual(result['cards'][0]['data']['spending_eur'], 400)
        self.assertEqual(result['cards'][0]['data']['categories'][0]['category'], 'restaurants')
        previous = {'name': 'category_reduction', 'arguments': {**args, 'category': 'restaurants', 'reduction_percent': 20}}
        self.ledger.conversation.return_value = previous
        self.provider.complete.return_value = call('category_reduction', {**previous['arguments'], 'reduction_percent': 10})
        result = await self.ask('What about 10% instead?')
        self.assertEqual(result['cards'][0]['data']['potential_reduction_eur'], 40)
        self.assertEqual(self.provider.complete.await_count, 2)


if __name__ == '__main__':
    unittest.main()
