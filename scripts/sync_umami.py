"""Validate and persist the fixed public Umami summary (no credentials required).

Archives are whole-source snapshots: replace, never add the previous total again.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

DOMAIN = 'hcmx1994.github.io'
FIELDS = {'schema_version', 'source', 'website_id', 'domain', 'captured_at',
          'started_at', 'timezone', 'current_month', 'current_month_visitors',
          'totals', 'countries', 'cities'}


def count(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2**53 - 1:
        raise ValueError('Invalid count')
    return value


def instant(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Missing timezone')
    return parsed


def country(value):
    if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[A-Z]{2}', value)):
        raise ValueError('Invalid country code')
    return value


def validate(data, website_id, previous=None, now=None):
    if set(data) != FIELDS:
        raise ValueError('Unexpected summary fields; only approved aggregates may be published')
    if (data['schema_version'] != 1 or data['source'] != 'Umami'
            or data['website_id'] != website_id or data['domain'] != DOMAIN
            or data['timezone'] != 'Europe/London'):
        raise ValueError('Wrong website or schema')
    stamp = instant(data['captured_at'])
    now = now or datetime.now(timezone.utc)
    # Allow small clock skew between the hosting platform and the backup runner.
    if (stamp - now).total_seconds() > 60:
        raise ValueError('Future capture time')
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', data['current_month']):
        raise ValueError('Invalid current month')
    from zoneinfo import ZoneInfo
    if stamp.astimezone(ZoneInfo('Europe/London')).strftime('%Y-%m') != data['current_month']:
        raise ValueError('Month does not match capture time')
    if set(data['totals']) != {'visits', 'pageviews'}:
        raise ValueError('Unexpected total fields')
    visits, views = (count(data['totals'][key]) for key in ('visits', 'pageviews'))
    if visits > views or count(data['current_month_visitors']) > visits:
        raise ValueError('Inconsistent counts')
    if visits:
        if not data['started_at'] or instant(data['started_at']) > stamp:
            raise ValueError('Missing or invalid tracking start')
    elif data['started_at'] is not None:
        raise ValueError('Empty data must have no first event')
    countries, cities, seen = {}, defaultdict(int), set()
    for row in data['countries']:
        if set(row) != {'code', 'visits'} or country(row['code']) in countries:
            raise ValueError('Invalid or duplicate country')
        countries[row['code']] = count(row['visits'])
    for row in data['cities']:
        if set(row) != {'country', 'name', 'visits'}:
            raise ValueError('Unexpected city fields')
        code, name = country(row['country']), row['name']
        if name is not None and (not isinstance(name, str) or len(name) > 160 or re.search(r'[\x00-\x1f]', name)):
            raise ValueError('Invalid city name')
        key = (code, name)
        if key in seen:
            raise ValueError('Duplicate city')
        seen.add(key)
        cities[code] += count(row['visits'])
    if sum(countries.values()) != visits or dict(cities) != countries:
        raise ValueError('Incomplete or inconsistent geography')
    if previous:
        validate(previous, website_id, now=now)
        if stamp < instant(previous['captured_at']):
            raise ValueError('Stale snapshot')
        if previous['started_at'] and data['started_at'] != previous['started_at']:
            raise ValueError('Tracking start changed; inspect for retention, reset or migration')
        if any(data['totals'][k] < previous['totals'][k] for k in ('visits', 'pageviews')):
            raise ValueError('Lifetime totals decreased; keep the previous archive')
        old_places = {row['code']: row['visits'] for row in previous['countries']}
        if any(countries.get(code, 0) < total for code, total in old_places.items()):
            raise ValueError('Historical geography decreased; inspect before replacing')
        old_cities = {(r['country'], r['name']): r['visits'] for r in previous['cities']}
        new_cities = {(r['country'], r['name']): r['visits'] for r in data['cities']}
        if any(new_cities.get(key, 0) < total for key, total in old_cities.items()):
            raise ValueError('Historical city counts decreased; inspect before replacing')
    return data


def save_snapshot(data, target, website_id, now=None):
    target = Path(target)
    previous = json.loads(target.read_text(encoding='utf-8')) if target.exists() else None
    validate(data, website_id, previous, now)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    handle, temp = tempfile.mkstemp(prefix=target.name + '.', dir=target.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--website-id', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path != '/api/homepage-summary'):
        raise ValueError('Use the fixed HTTPS public summary URL')
    request = urllib.request.Request(args.url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.geturl() != args.url:
            raise ValueError('Unexpected redirect')
        if response.headers.get_content_type() != 'application/json':
            raise ValueError('Expected JSON')
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Summary exceeds expected size')
    data = json.loads(raw)
    if (datetime.now(timezone.utc) - instant(data['captured_at'])).total_seconds() > 86400:
        raise ValueError('Endpoint returned an outdated snapshot')
    save_snapshot(data, args.output, args.website_id)
    print('Saved validated aggregate snapshot; no visitor-level data included.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # No response bodies/credentials in logs. Leave the last archive intact.
        print(f'Visitor backup failed ({type(exc).__name__}); existing archive preserved.', file=sys.stderr)
        sys.exit(1)
