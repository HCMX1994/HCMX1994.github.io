"""Verify map counts, missing geography, safe labels and calendar rollover."""
import copy
import unittest
from datetime import datetime, timezone

from archive_visitors import import_month, new_archive
from test_archive_visitors import sample
from visitor_panel import render_panel, summarize

REFERENCE = {'GB': {'name': 'United Kingdom', 'x': 353, 'y': 69}}
NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)


class VisitorPanelTests(unittest.TestCase):
    def archive(self):
        month = sample()
        month.update(captured_at='2026-09-24T12:00:00Z', complete=False)
        return import_month(import_month(new_archive(), sample('2026-08')), month)

    def test_all_months_add_visits_not_unique_visitors(self):
        data = summarize(self.archive(), REFERENCE, NOW)
        self.assertEqual(data['visits'], 6)
        self.assertEqual(data['current_visitors'], 2)
        self.assertEqual(data['countries'][0]['visits'], 6)
        self.assertEqual(data['countries'][0]['cities'][0]['visits'], 6)
        self.assertNotIn('total_visitors', data)

    def test_missing_current_month_is_not_zero_or_last_month(self):
        data = summarize(self.archive(), REFERENCE, datetime(2026, 10, 1, tzinfo=timezone.utc))
        self.assertIsNone(data['current_visitors'])
        self.assertEqual(data['visits'], 6)

    def test_unknown_and_unmapped_countries_stay_in_denominator(self):
        month = sample('2026-08')
        for row in [*month['countries'], *month['cities']]: row['country'] = None
        archive = import_month(self.archive(), month)
        data = summarize(archive, {}, NOW)
        self.assertEqual(data['visits'], 6)
        self.assertEqual(sum(row['visits'] for row in data['countries']), 6)
        self.assertTrue(all(row['point'] is None for row in data['countries']))
        self.assertEqual(sum(row['visits'] for row in data['countries'] if not row['code']), 3)

    def test_same_city_name_in_different_countries_remains_separate(self):
        archive = self.archive()
        month = copy.deepcopy(archive['months'][0])
        for row in [*month['countries'], *month['cities']]: row['country'] = 'US'
        data = summarize(import_month(archive, month), REFERENCE, NOW)
        self.assertEqual(len(data['countries']), 2)
        self.assertEqual([row['cities'][0]['visits'] for row in data['countries']], [3, 3])

    def test_render_is_safe_and_umami_only(self):
        archive = self.archive()
        archive['months'][0]['cities'][0]['city'] = '</script><img src=x onerror=alert(1)>'
        panel = render_panel(archive, NOW)
        self.assertNotIn('</script><img', panel)
        self.assertNotIn('mapmyvisitors', panel.lower())
        self.assertIn('Total archived visits', panel)
        self.assertIn('2026-09', panel)
        self.assertIn('not precise visitor locations', panel)


if __name__ == '__main__':
    unittest.main()
