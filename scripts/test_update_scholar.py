import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import update_scholar as updater

class ScholarTests(unittest.TestCase):
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

if __name__=='__main__':
    unittest.main()
