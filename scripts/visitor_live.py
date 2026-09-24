"""Combine the frozen Cloud baseline and one self-hosted lifetime snapshot."""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from sync_umami import validate

SITE = 'd8c1f3fa-cb3e-4753-9aba-a78aa9a99836'
CLOUD = '3000b10a-b4af-481b-ac2b-a6a611908de4'
ENDPOINT = 'https://homepage-umami.vercel.app/api/homepage-summary'
ROOT = Path(__file__).resolve().parents[1]


def combine(baseline, live, reference, now=None):
    now = now or datetime.now(timezone.utc)
    validate(baseline, CLOUD, now=now)
    validate(live, SITE, now=now)
    countries, cities = defaultdict(int), defaultdict(int)
    for snapshot in (baseline, live):
        for row in snapshot['countries']:
            countries[row['code'] or ''] += row['visits']
        for row in snapshot['cities']:
            cities[(row['country'] or '', row['name'] or 'Unknown city')] += row['visits']
    rows = []
    for code, visits in countries.items():
        ref = reference.get(code, {})
        rows.append({'code': code, 'name': ref.get('name', code or 'Unknown location'),
                     'visits': visits,
                     'point': [ref['x'], ref['y']] if ref and 0 <= ref['y'] <= 310 else None,
                     'cities': sorted([{'name': name, 'visits': n} for (c, name), n in cities.items() if c == code], key=lambda r: (-r['visits'], r['name']))})
    month = now.astimezone(ZoneInfo('Europe/London')).strftime('%Y-%m')
    # Unique visitors cannot be deduplicated across two independently salted services.
    # For the migration month label the new service's count explicitly.
    migration_month = baseline['current_month']
    return {'visits': baseline['totals']['visits'] + live['totals']['visits'],
            'current_month': month,
            'current_visitors': live['current_month_visitors'] if live['current_month'] == month else None,
            'current_label': 'Visitors since 24 Sep' if month == migration_month else 'Visitors',
            'timezone': 'Europe/London', 'tracking_started': baseline['started_at'][:10],
            'captured_at': live['captured_at'], 'months': [],
            'countries': sorted(rows, key=lambda r: (-r['visits'], r['name'])),
            'service': {'url': ENDPOINT, 'website_id': SITE, 'baseline': baseline, 'snapshot': live},
            'reference': reference}


def load_data(now=None):
    read = lambda file: json.loads((ROOT / 'assets/data' / file).read_text(encoding='utf-8'))
    return combine(read('umami-baseline.json'), read('umami-live.json'), read('visitor-countries.json')['countries'], now)
