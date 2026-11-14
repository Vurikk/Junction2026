"""Coach selection and engine-backed financial checks; no local data required."""
import unittest
from types import SimpleNamespace
from backend.coach import answer
from backend.financial import history, plan
from backend import test_financial


class CoachTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_financial.FinancialTests()
        self.inputs = self.fixture.assumptions()
        self.goals = [SimpleNamespace(id='one', name='Bike', amount_eur=200, priority='flexible')]
        self.analysis = plan(self.inputs, self.goals)
        self.history = history(self.fixture.customer(), 'month')

    def ask(self, question):
        return answer(question, self.analysis, self.goals, self.history)

    def test_selection(self):
        for question, kind in [('Spending by category', 'categories'), ('historical average', 'average'),
                               ('Daily allowance', 'allowance'), ('Goal progress', 'goals'),
                               ('What if I add a goal?', 'scenario'), ('hello', 'help')]:
            self.assertEqual(self.ask(question)['kind'], kind)

    def test_amounts_and_exclusions(self):
        self.assertEqual(self.ask('categories')['rows'], [{'label': 'unknown', 'value': 30.0}])
        self.assertIn('EUR 13.33', self.ask('average')['text'])
        self.assertIn('EUR 6.66/day', self.ask('daily')['text'])
        self.assertIn('EUR 46.62/week', self.ask('weekly')['text'])
        self.assertIn('saved progress is unknown', self.ask('goals')['text'])

    def test_missing(self):
        result = answer('daily', plan({}, []), [])
        self.assertIn('essential bills', result['text'])
        self.assertNotIn('EUR', result['text'])
        self.assertIn('needed', answer('categories', self.analysis, [], None)['text'])

    def test_category_only_and_absent_latest_category(self):
        self.assertEqual(self.ask('How much on unknown?')['rows'], [{'label': 'unknown', 'value': 30.0}])
        absent = self.ask('How much on housing?')
        self.assertEqual(absent['kind'], 'categories')
        self.assertEqual(absent['rows'], [])
        self.assertIn('No included payments', absent['text'])
        self.assertEqual(self.ask('weekly historical average')['kind'], 'average')

    def test_unknown_values_and_mortgage(self):
        self.assertIn('unknown', self.ask('current balance')['text'])
        for available in (True, False):
            result = answer('mortgage monthly payment', self.analysis, self.goals, mortgage_available=available)
            self.assertIn('Monthly repayments are unknown', result['text'])
            self.assertEqual(result['text'].startswith('Linked'), available)

    def test_preview_protects_priority_and_does_not_mutate(self):
        preview = SimpleNamespace(id='preview', name='Repair', amount_eur=300, priority='critical')
        simulated = plan(self.inputs, [*self.goals, preview])
        result = answer('preview', simulated, [*self.goals, preview], preview={'name': 'Repair'})
        self.assertIn('Repair: EUR 300.00', result['text'])
        self.assertIn('Bike: EUR 0.00', result['text'])
        self.assertEqual(len(self.goals), 1)
        self.assertEqual(plan(self.inputs, self.goals), self.analysis)


class CoachApiTests(unittest.TestCase):
    def test_customers_preview_and_analysis_compatibility(self):
        from backend.main import Assumptions, CoachInput, analyze_goals, coach, create_goal
        fixture = test_financial.FinancialTests()
        state = SimpleNamespace(customers={key: fixture.customer() for key in ('a', 'b')},
                                goals={'a': [], 'b': []},
                                assumptions={key: Assumptions(**fixture.assumptions()).model_dump(mode='json') for key in ('a', 'b')})
        for customer in state.customers.values():
            customer.has_mortgage_data = lambda: False
        request = SimpleNamespace(app=SimpleNamespace(state=state))
        payload = CoachInput(question='what if', scenario={'name': 'Bike', 'amount_eur': '200', 'priority': 'flexible'})
        for key in ('a', 'b'):
            result = coach(request, key, payload)
            self.assertIn('Bike: EUR 200.00', result['text'])
            self.assertEqual(state.goals[key], [])
        create_goal(request, 'a', payload.scenario)
        analyzed = analyze_goals(request, 'a')
        self.assertIn('Bike', analyzed['coach_message'])
        self.assertEqual(analyzed['total_target_eur'], '200.00')
        self.assertEqual(state.goals['b'], [])


if __name__ == '__main__':
    unittest.main()
