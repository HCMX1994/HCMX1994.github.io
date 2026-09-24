import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from sync_umami import save_snapshot, validate

NOW = datetime(2027, 5, 1, 12, tzinfo=timezone.utc)
SITE = '00000000-0000-4000-8000-000000000001'


def sample():
    return {'schema_version': 1, 'source': 'Umami', 'website_id': SITE,
            'domain': 'hcmx1994.github.io', 'captured_at': '2027-05-01T11:00:00+00:00',
            'started_at': '2026-09-24T18:00:00+00:00', 'timezone': 'Europe/London',
            'current_month': '2027-05', 'current_month_visitors': 1,
            'totals': {'visits': 10, 'pageviews': 18},
            'countries': [{'code': 'GB', 'visits': 8}, {'code': None, 'visits': 2}],
            'cities': [{'country': 'GB', 'name': 'London', 'visits': 6},
                       {'country': 'GB', 'name': None, 'visits': 2},
                       {'country': None, 'name': None, 'visits': 2}]}


class BackupTests(unittest.TestCase):
    def test_older_than_six_months_retained(self):
        saved = validate(sample(), SITE, now=NOW)
        self.assertEqual(saved['totals']['visits'], 10)
        self.assertEqual(saved['started_at'], '2026-09-24T18:00:00+00:00')

    def test_repeat_save_replaces_without_double_counting(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'summary.json'
            save_snapshot(sample(), path, SITE, NOW)
            save_snapshot(sample(), path, SITE, NOW)
            self.assertEqual(json.loads(path.read_text())['totals']['visits'], 10)

    def test_invalid_snapshot_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'summary.json'
            save_snapshot(sample(), path, SITE, NOW)
            before = path.read_bytes()
            changed = sample()
            changed['countries'] = changed['countries'][:1]
            with self.assertRaises(ValueError):
                save_snapshot(changed, path, SITE, NOW)
            self.assertEqual(path.read_bytes(), before)

    def test_does_not_accept_reset_or_retention(self):
        old = sample()
        new = copy.deepcopy(old)
        new['totals'] = {'visits': 0, 'pageviews': 0}
        new['current_month_visitors'] = 0
        new['started_at'] = None
        new['countries'], new['cities'] = [], []
        with self.assertRaises(ValueError):
            validate(new, SITE, old, NOW)

    def test_rejects_stale_wrong_site_and_extra_sensitive_fields(self):
        for mutation in [lambda d: d.update(captured_at='2027-05-01T10:00:00Z'),
                         lambda d: d.update(website_id='another-site'),
                         lambda d: d.update(ip='192.0.2.1'),
                         lambda d: d['cities'][0].update(session_id='not-public')]:
            changed = sample()
            mutation(changed)
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    validate(changed, SITE, sample(), NOW)

    def test_places_include_unknown_in_total_and_proportions(self):
        data = validate(sample(), SITE, now=NOW)
        self.assertEqual(sum(r['visits'] for r in data['countries']), 10)
        self.assertEqual(data['countries'][0]['visits'] / data['totals']['visits'], .8)

    def test_month_rollover_preserves_history_and_changes_only_monthly_visitors(self):
        old = sample()
        new = copy.deepcopy(old)
        new.update(captured_at='2027-06-01T00:00:00Z', current_month='2027-06', current_month_visitors=0)
        validate(new, SITE, old, datetime(2027, 6, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(new['totals'], old['totals'])
        self.assertEqual(new['countries'], old['countries'])

    def test_empty_new_database_can_receive_its_first_visit(self):
        old = sample()
        old.update(started_at=None, current_month_visitors=0, totals={'visits': 0, 'pageviews': 0}, countries=[], cities=[])
        new = sample()
        new['started_at'] = '2027-05-01T11:00:00+00:00'
        validate(new, SITE, old, NOW)

    def test_city_history_cannot_silently_disappear_with_unchanged_country_total(self):
        new = sample()
        new['cities'][0]['name'] = 'Another city'
        with self.assertRaises(ValueError):
            validate(new, SITE, sample(), NOW)


if __name__ == '__main__':
    unittest.main()
