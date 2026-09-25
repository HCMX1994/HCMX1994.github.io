"""Checks for wrong-profile reads, misleading counters and failure-safe caching."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from update_wos import PROFILE_URL, RESEARCHER_ID, parse_observation, refresh, render_panel

NOW = datetime(2026, 9, 26, 8, tzinfo=timezone.utc)


class ReviewSnapshotTests(unittest.TestCase):
    def observation(self, count='211'):
        return {'url': PROFILE_URL, 'name': 'WOS Top Header Xuekang  Liu',
                'identity': 'Web of Science ResearcherID : ' + RESEARCHER_ID,
                'rows': [{'label': 'Verified peer reviews', 'count': count}]}

    def test_exact_metric_and_profile(self):
        self.assertEqual(parse_observation(self.observation('1,211')), 1211)
        for key, value in [('url', 'https://www.webofscience.com/wos/author/record/OTHER'),
                           ('name', 'Another Researcher'), ('identity', 'OTHER')]:
            wrong = self.observation()
            wrong[key] = value
            with self.assertRaises(ValueError):
                parse_observation(wrong)
        wrong = self.observation()
        wrong['rows'][0]['label'] = 'Verified editor records'
        with self.assertRaises(ValueError):
            parse_observation(wrong)

    def test_loading_and_ambiguous_values_are_not_zero(self):
        for count in ('', '—', 'Loading', '211+', '-1', '21,1', '2.11'):
            with self.assertRaises(ValueError):
                parse_observation(self.observation(count))
        for rows in ([], self.observation()['rows'] * 2):
            wrong = self.observation()
            wrong['rows'] = rows
            with self.assertRaises(ValueError):
                parse_observation(wrong)

    def test_failure_preserves_count_and_original_date(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'wos.json'
            refresh(output, lambda: 211, NOW)
            original = output.read_bytes()
            tomorrow = datetime(2026, 9, 27, 8, tzinfo=timezone.utc)
            def unavailable():
                raise TimeoutError('unavailable')
            for fetch in (unavailable, lambda: 0, lambda: None):
                with self.assertRaises((ValueError, TimeoutError)):
                    refresh(output, fetch, tomorrow)
                self.assertEqual(output.read_bytes(), original)

    def test_daily_skip_and_next_day_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'wos.json'
            refresh(output, lambda: 211, NOW)
            def unnecessary():
                self.fail('Should not request WoS twice in the same UTC day')
            refresh(output, unnecessary, NOW)
            data = refresh(output, lambda: 212, datetime(2026, 9, 27, 8, tzinfo=timezone.utc))
            self.assertEqual(data['verified_peer_reviews'], 212)
            self.assertIn('27 Sep 2026', render_panel(output, NOW))

    def test_manual_seed_does_not_skip_first_automated_read(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'wos.json'
            data = refresh(output, lambda: 211, NOW)
            data['method'] = 'public-profile-manual-check'
            output.write_text(json.dumps(data), encoding='utf-8')
            self.assertEqual(refresh(output, lambda: 212, NOW)['verified_peer_reviews'], 212)
            stale = render_panel(output, datetime(2026, 10, 1, tzinfo=timezone.utc))
            self.assertIn('Update pending', stale)
            self.assertIn('26 Sep 2026', stale)
            self.assertIn(PROFILE_URL, stale)
            output.write_text('{}', encoding='utf-8')
            fallback = render_panel(output, NOW)
            self.assertIn('View peer reviews', fallback)
            self.assertNotIn('<strong>0', fallback)


if __name__ == '__main__':
    unittest.main()
