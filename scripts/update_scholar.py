"""Refresh Scholar metrics once, preserving the snapshot on any failure.

Use SerpApi when SERPAPI_API_KEY is configured; otherwise try the public profile.
API credentials stay in the runner environment and are never written or logged.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

AUTHOR_ID = 'vj_3bhQAAAAJ'
URL = f'https://scholar.google.com/citations?user={AUTHOR_ID}&hl=en'
OUTPUT = Path(__file__).resolve().parents[1] / 'assets/data/scholar.json'
METRIC_KEYS = {'citations', 'h_index', 'i10_index'}


def validate_metrics(metrics):
    if set(metrics) != METRIC_KEYS or any(type(value) is not int or value < 0 for value in metrics.values()):
        raise ValueError('Missing or invalid Scholar metrics')
    if metrics['h_index'] > metrics['citations'] or metrics['i10_index'] * 10 > metrics['citations']:
        raise ValueError('Inconsistent Scholar metrics')
    return metrics

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
    return validate_metrics(result)


def parse_serpapi(data):
    if data.get('error') or data.get('search_metadata', {}).get('status') != 'Success':
        raise ValueError('SerpApi search did not succeed')
    if data.get('search_parameters', {}).get('author_id') != AUTHOR_ID:
        raise ValueError('Unexpected Scholar author')
    metrics = {}
    for row in data.get('cited_by', {}).get('table', []):
        for key in METRIC_KEYS.intersection(row):
            if key in metrics:
                raise ValueError('Duplicate Scholar metric')
            metrics[key] = row[key].get('all')
    return validate_metrics(metrics)


def fetch_metrics(api_key):
    if api_key:
        query = urlencode({'engine': 'google_scholar_author', 'author_id': AUTHOR_ID,
                           'hl': 'en', 'api_key': api_key})
        request = Request('https://serpapi.com/search.json?' + query,
                          headers={'Accept': 'application/json'})
        with urlopen(request, timeout=45) as response:
            return parse_serpapi(json.loads(response.read(2_000_000)))
    request = Request(URL, headers={'User-Agent': 'AcademicProfileMetrics/1.0 (daily public profile snapshot)'})
    with urlopen(request, timeout=30) as response:
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected response type')
        return parse_metrics(response.read(2_000_000).decode('utf-8'))

def main():
    api_key = os.environ.get('SERPAPI_API_KEY', '').strip()
    provider = 'SerpApi' if api_key else 'public profile'
    try:
        metrics = fetch_metrics(api_key)
        snapshot = {'author_id': AUTHOR_ID, **metrics, 'updated_at': datetime.now(timezone.utc).date().isoformat(), 'source': URL}
        temporary = OUTPUT.with_suffix('.tmp')
        temporary.write_text(json.dumps(snapshot, indent=2) + '\n', encoding='utf-8')
        temporary.replace(OUTPUT)
        print(f'Updated Scholar metrics successfully via {provider}.')
        return 0
    except Exception as error:
        # HTTP errors can contain the API key in their URL; never print error text.
        detail = f'HTTP {error.code}' if isinstance(error, HTTPError) else type(error).__name__
        print(f'Scholar refresh failed via {provider} ({detail}); previous snapshot preserved.', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
