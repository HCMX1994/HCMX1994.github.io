"""Fetch a public Google Scholar profile once; preserve the snapshot on any failure.

No credentials, browser automation, CAPTCHA solving or retry/proxy mechanisms.
"""
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

AUTHOR_ID = 'vj_3bhQAAAAJ'
URL = f'https://scholar.google.com/citations?user={AUTHOR_ID}&hl=en'
OUTPUT = Path(__file__).resolve().parents[1] / 'assets/data/scholar.json'

class MetricsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.table_depth = 0
        self.in_cell = False
        self.cell = ''
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            if attrs.get('id') == 'gsc_rsb_st':
                self.in_table = True
            if self.in_table:
                self.table_depth += 1
        if self.in_table and tag == 'tr':
            self.row = []
        if self.in_table and tag == 'td':
            self.in_cell = True
            self.cell = ''

    def handle_data(self, data):
        if self.in_cell:
            self.cell += data

    def handle_endtag(self, tag):
        if self.in_table and tag == 'td':
            self.row.append(self.cell.strip())
            self.in_cell = False
        if self.in_table and tag == 'tr':
            self.rows.append(self.row)
        if self.in_table and tag == 'table':
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_table = False

def parse_metrics(html):
    parser = MetricsParser()
    parser.feed(html)
    labels = {'Citations': 'citations', 'h-index': 'h_index', 'i10-index': 'i10_index'}
    result = {}
    for row in parser.rows:
        if len(row) >= 2 and row[0] in labels:
            value = row[1].replace(',', '').replace('\u00a0', '').strip()
            if not re.fullmatch(r'\d+', value):
                raise ValueError('Non-numeric Scholar metric')
            result[labels[row[0]]] = int(value)
    if set(result) != set(labels.values()):
        raise ValueError('Scholar metrics unavailable; possible blocked request or changed markup')
    if result['h_index'] > result['citations'] or result['i10_index'] * 10 > result['citations']:
        raise ValueError('Inconsistent Scholar metrics')
    return result

def main():
    try:
        request = Request(URL, headers={'User-Agent': 'AcademicProfileMetrics/1.0 (daily public profile snapshot)'})
        with urlopen(request, timeout=30) as response:
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Unexpected response type')
            metrics = parse_metrics(response.read(2_000_000).decode('utf-8'))
        snapshot = {'author_id': AUTHOR_ID, **metrics, 'updated_at': datetime.now(timezone.utc).date().isoformat(), 'source': URL}
        temporary = OUTPUT.with_suffix('.tmp')
        temporary.write_text(json.dumps(snapshot, indent=2) + '\n', encoding='utf-8')
        temporary.replace(OUTPUT)
        print('Updated Scholar metrics successfully.')
        return 0
    except Exception as error:
        # No response body, credentials or request details are printed.
        print(f'Scholar refresh failed ({type(error).__name__}); previous snapshot preserved.', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
