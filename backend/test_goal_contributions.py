from datetime import date
from types import SimpleNamespace
import unittest
from backend.goal_contributions import contribution_demo


class ContributionTests(unittest.TestCase):
    def test_six_completed_months_demo_only_and_no_mutation(self):
        goal = SimpleNamespace(id='one', name='New car', amount_eur=12000)
        result = contribution_demo([goal], date(2026, 11, 15))
        self.assertIsNone(result['actual_saved_eur'])
        self.assertEqual(result['kind'], 'demo_planned')
        series = result['goals'][0]
        self.assertEqual([item['month'] for item in series['months']],
                         ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'])
        self.assertTrue(all(item['planned_eur'] == 400 for item in series['months']))
        self.assertEqual(series['total_planned_eur'], 2400)
        self.assertEqual(goal.amount_eur, 12000)
        self.assertEqual(contribution_demo([SimpleNamespace(id='two', name='Trip')])['goals'], [])
        self.assertEqual(contribution_demo([goal], date(2026, 1, 1))['goals'][0]['months'][0]['month'], '2025-07')
