"""Protect archived totals against repeated, partial and incompatible imports."""
import copy
import tempfile
import unittest
from pathlib import Path

from archive_visitors import import_month, new_archive, read_export, render, validate_archive


def sample(month='2026-09'):
    return {'month':month,'timezone':'Europe/London','captured_at':'2026-10-02T12:00:00Z',
            'complete':True,'totals':{'visitors':2,'visits':3,'pageviews':4},
            'countries':[{'country':'GB','city':None,'visitors':2,'visits':3,'pageviews':4}],
            'cities':[{'country':'GB','city':'London','visitors':2,'visits':3,'pageviews':4}],
            'source_sha256':{}}


class ArchiveTests(unittest.TestCase):
    def test_repeated_month_is_replaced_not_added(self):
        first=import_month(new_archive(),sample())
        second=import_month(first,sample())
        self.assertEqual(first,second)
        self.assertEqual(sum(m['totals']['visits'] for m in second['months']),3)

    def test_nonoverlapping_months_preserve_individual_visitors(self):
        first=import_month(new_archive(),sample('2026-08'))
        result=import_month(first,sample())
        self.assertEqual(len(result['months']),2)
        self.assertEqual([m['totals']['visitors'] for m in result['months']],[2,2])
        self.assertNotIn('total_visitors',result)

    def test_incomplete_export_is_rejected_without_mutating_archive(self):
        first=import_month(new_archive(),sample())
        before=copy.deepcopy(first)
        broken=sample();broken['cities']=[]
        with self.assertRaisesRegex(ValueError,'do not match'): import_month(first,broken)
        self.assertEqual(first,before)

    def test_country_city_mismatch_is_rejected(self):
        broken=sample();broken['cities'][0]['country']='US'
        with self.assertRaisesRegex(ValueError,'disagree'): import_month(new_archive(),broken)

    def test_current_month_is_not_complete(self):
        broken=sample();broken['captured_at']='2026-09-24T12:00:00Z'
        with self.assertRaisesRegex(ValueError,'cannot be marked complete'): import_month(new_archive(),broken)
        broken['complete']=False
        validate_archive(import_month(new_archive(),broken))

    def test_corrections_and_old_snapshots_require_attention(self):
        first=import_month(new_archive(),sample())
        old=sample();old['captured_at']='2026-10-01T12:00:00Z'
        with self.assertRaisesRegex(ValueError,'older'): import_month(first,old)
        smaller=sample()
        for row in [smaller['totals'],*smaller['countries'],*smaller['cities']]: row.update(visitors=1,visits=1,pageviews=1)
        with self.assertRaisesRegex(ValueError,'decreased'): import_month(first,smaller)
        validate_archive(import_month(first,smaller,allow_correction=True))

    def test_unknown_location_is_kept(self):
        row=sample()
        for location in [*row['countries'],*row['cities']]: location.update(country=None,city=None)
        result=import_month(new_archive(),row)
        self.assertEqual(result['months'][0]['countries'][0]['visits'],3)

    def test_csv_schema_duplicate_rows_and_negative_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'country.csv'
            header='name,pageviews,visitors,visits,bounces,totaltime\n'
            path.write_text(header+'GB,4,2,3,0,0\n',encoding='utf-8-sig')
            rows,_=read_export(path,'countries')
            self.assertEqual(rows[0]['visits'],3)
            path.write_text(header+'GB,4,2,3,0,0\nGB,1,1,1,0,0\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate'): read_export(path,'countries')
            path.write_text(header+'GB,4,-2,3,0,0\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'non-negative'): read_export(path,'countries')

    def test_export_labels_cannot_inject_html(self):
        row=sample();row['cities'][0]['city']='</script><img src=x onerror=alert(1)>'
        document=render(import_month(new_archive(),row))
        self.assertNotIn('</script><img',document)
        self.assertIn('\\u003c/script>',document)


if __name__=='__main__':
    unittest.main()
