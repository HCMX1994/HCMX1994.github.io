import copy
import unittest
from datetime import datetime, timezone
from test_sync_umami import sample, NOW
from visitor_live import combine, SITE, CLOUD

class LifetimeTests(unittest.TestCase):
    def sources(self):
        live=sample(); live['website_id']=SITE
        baseline=copy.deepcopy(live); baseline['website_id']=CLOUD
        baseline.update(captured_at='2026-09-24T18:30:00Z', current_month='2026-09')
        return baseline,live

    def test_sources_are_added_once_and_locations_reconcile(self):
        baseline,live=self.sources()
        for _ in range(3):
            data=combine(baseline,live,{},NOW)
            self.assertEqual(data['visits'],20)
            self.assertEqual(sum(r['visits'] for r in data['countries']),20)
            self.assertEqual(sum(c['visits'] for r in data['countries'] for c in r['cities']),20)
            self.assertEqual(data['current_visitors'],1)

    def test_rollover_does_not_reuse_previous_month(self):
        data=combine(*self.sources(),{},datetime(2027,6,1,tzinfo=timezone.utc))
        self.assertIsNone(data['current_visitors'])
        self.assertEqual(data['visits'],20)

    def test_migration_does_not_add_unique_visitor_counts(self):
        baseline,live=self.sources()
        live.update(current_month='2026-09',captured_at='2026-09-24T18:35:00Z')
        data=combine(baseline,live,{},datetime(2026,9,24,19,tzinfo=timezone.utc))
        self.assertEqual(data['current_label'],'Visitors since 24 Sep')
        self.assertEqual(data['current_visitors'],1)

if __name__=='__main__':unittest.main()
