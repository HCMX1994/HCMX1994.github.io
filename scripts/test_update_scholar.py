import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import update_scholar as updater

class ScholarTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'SERPAPI_API_KEY': ''})
        environment.start()
        self.addCleanup(environment.stop)

    def table(self, citations='1,234', h='12', i10='13'):
        return f'<table id="gsc_rsb_st"><tr><td>Citations</td><td class="gsc_rsb_std">{citations}</td><td>100</td></tr><tr><td>h-index</td><td>{h}</td><td>9</td></tr><tr><td>i10-index</td><td>{i10}</td><td>9</td></tr></table>'

    def test_all_time_column_and_thousands(self):
        self.assertEqual(updater.parse_metrics(self.table()), {'citations':1234,'h_index':12,'i10_index':13})

    def test_challenge_and_partial_response_rejected(self):
        for html in ['<html>unusual traffic</html>', '<table id="gsc_rsb_st"><tr><td>Citations</td><td>1234</td></tr></table>', self.table('unknown')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                updater.parse_metrics(html)

    def test_network_failure_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'scholar.json'
            original='{"citations":595,"updated_at":"2026-09-24"}'
            output.write_text(original)
            with patch.object(updater,'OUTPUT',output), patch.object(updater,'urlopen',side_effect=TimeoutError):
                self.assertEqual(updater.main(),1)
            self.assertEqual(output.read_text(),original)

    def test_valid_response_updates_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'scholar.json'
            from unittest.mock import MagicMock
            response=MagicMock()
            response.__enter__.return_value=response
            response.headers={'Content-Type':'text/html; charset=utf-8'}
            response.read.return_value=self.table().encode()
            with patch.object(updater,'OUTPUT',output), patch.object(updater,'urlopen',return_value=response):
                self.assertEqual(updater.main(),0)
            self.assertEqual(json.loads(output.read_text())['citations'],1234)
            self.assertFalse(output.with_suffix('.tmp').exists())

    def api_result(self):
        return {
            'search_metadata': {'status': 'Success'},
            'search_parameters': {'author_id': updater.AUTHOR_ID},
            'cited_by': {'table': [
                {'i10_index': {'all': 12, 'since_2021': 10}},
                {'citations': {'all': 595, 'since_2021': 580}},
                {'h_index': {'all': 12, 'since_2021': 11}},
            ]},
        }

    def test_serpapi_reads_all_time_values_by_name(self):
        self.assertEqual(updater.parse_serpapi(self.api_result()),
                         {'citations': 595, 'h_index': 12, 'i10_index': 12})

    def test_serpapi_rejects_wrong_author_errors_and_invalid_data(self):
        cases = []
        wrong_author = self.api_result()
        wrong_author['search_parameters']['author_id'] = 'somebody_else'
        cases.append(wrong_author)
        cases.append({'error': 'Quota exceeded'})
        pending = self.api_result()
        pending['search_metadata']['status'] = 'Processing'
        cases.append(pending)
        partial = self.api_result()
        partial['cited_by']['table'].pop()
        cases.append(partial)
        for invalid in [True, -1, '595', 595.5, None]:
            result = self.api_result()
            result['cited_by']['table'][1]['citations']['all'] = invalid
            cases.append(result)
        duplicate = self.api_result()
        duplicate['cited_by']['table'].append({'citations': {'all': 600}})
        cases.append(duplicate)
        for result in cases:
            with self.subTest(result=result), self.assertRaises(ValueError):
                updater.parse_serpapi(result)

    def test_api_key_selects_serpapi_without_publishing_key(self):
        from unittest.mock import MagicMock
        from urllib.parse import parse_qs, urlparse
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'scholar.json'
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = json.dumps(self.api_result()).encode()
            with patch.dict(os.environ, {'SERPAPI_API_KEY': 'test-secret'}), \
                 patch.object(updater, 'OUTPUT', output), \
                 patch.object(updater, 'urlopen', return_value=response) as request:
                self.assertEqual(updater.main(), 0)
            self.assertEqual(request.call_count, 1)
            url = urlparse(request.call_args.args[0].full_url)
            self.assertEqual(url.netloc, 'serpapi.com')
            self.assertEqual(parse_qs(url.query)['author_id'], [updater.AUTHOR_ID])
            self.assertEqual(parse_qs(url.query)['api_key'], ['test-secret'])
            snapshot = json.loads(output.read_text())
            self.assertEqual(snapshot['citations'], 595)
            self.assertEqual(snapshot['source'], updater.URL)
            self.assertNotIn('test-secret', output.read_text())

    def test_api_http_error_preserves_data_and_redacts_key(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'scholar.json'
            original = '{"citations":595,"updated_at":"2026-09-24"}'
            output.write_text(original)
            error = HTTPError('https://serpapi.com/search.json?api_key=test-secret',
                              429, 'test-secret', {}, None)
            stderr = io.StringIO()
            with patch.dict(os.environ, {'SERPAPI_API_KEY': 'test-secret'}), \
                 patch.object(updater, 'OUTPUT', output), \
                 patch.object(updater, 'urlopen', side_effect=error) as request, \
                 patch('sys.stderr', stderr):
                self.assertEqual(updater.main(), 1)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(output.read_text(), original)
            self.assertIn('HTTP 429', stderr.getvalue())
            self.assertNotIn('test-secret', stderr.getvalue())

if __name__=='__main__':
    unittest.main()
