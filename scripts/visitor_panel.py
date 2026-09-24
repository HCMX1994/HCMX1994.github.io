"""Render the shared Umami-only footer from validated, saved monthly aggregates."""
import html
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from archive_visitors import validate_archive

ROOT = Path(__file__).resolve().parents[1]


def summarize(archive, reference, now=None):
    validate_archive(archive)
    now = now or datetime.now(timezone.utc)
    zone = archive['months'][0]['timezone'] if archive['months'] else 'Europe/London'
    current_key = now.astimezone(ZoneInfo(zone)).strftime('%Y-%m')
    current = next((m for m in archive['months'] if m['month'] == current_key), None)
    country_counts, city_counts = defaultdict(int), defaultdict(int)
    for month in archive['months']:
        for row in month['countries']:
            country_counts[row['country'] or ''] += row['visits']
        for row in month['cities']:
            city_counts[(row['country'] or '', row['city'] or 'Unknown city')] += row['visits']
    countries = []
    for code, visits in country_counts.items():
        point = reference.get(code, {})
        cities = [{'name': name, 'visits': count} for (country, name), count in city_counts.items() if country == code]
        countries.append({'code': code, 'name': point.get('name', code or 'Unknown location'), 'visits': visits,
                          'point': [point['x'], point['y']] if point and 0 <= point['y'] <= 310 else None,
                          'cities': sorted(cities, key=lambda row: (-row['visits'], row['name']))})
    return {'visits': sum(m['totals']['visits'] for m in archive['months']),
            'current_month': current_key, 'current_visitors': current['totals']['visitors'] if current else None,
            'timezone': zone, 'tracking_started': archive['tracking_started'],
            'captured_at': max((m['captured_at'] for m in archive['months']), default=None),
            'months': [m['month'] for m in archive['months']],
            'countries': sorted(countries, key=lambda row: (-row['visits'], row['name']))}


def render_panel(archive, now=None):
    reference = json.loads((ROOT / 'assets/data/visitor-countries.json').read_text(encoding='utf-8'))['countries']
    data = summarize(archive, reference, now)
    esc = lambda value: html.escape(str(value), quote=True)
    total = data['visits']
    share = lambda count: f'{100 * count / total:.1f}%' if total else '0.0%'
    known = sum(bool(row['code']) and row['visits'] > 0 for row in data['countries'])
    unmapped = sum(row['visits'] for row in data['countries'] if not row['point'])
    markers, options, rows = [], [], []
    for row in data['countries']:
        code, name, count = row['code'], esc(row['name']), row['visits']
        options.append(f'<option value="{esc(code or "unknown")}">{name} · {count:,}</option>')
        if row['point'] and count:
            x, y = row['point']
            radius = min(14, 4 + 2 * math.sqrt(count))
            label = f'{name}: {count:,} visits, {share(count)} of archived visits'
            markers.append(f'<g class="visitor-marker" role="button" tabindex="0" aria-label="{label}" aria-pressed="false" data-country="{esc(code)}" transform="translate({x} {y})"><title>{label}</title><circle class="visitor-marker-halo" r="{radius+3:.1f}"/><circle class="visitor-marker-dot" r="{radius:.1f}"/></g>')
    for row in data['countries'][:3]:
        rows.append(f'<tr><td>{esc(row["name"])}</td><td>{row["visits"]:,}</td><td>{share(row["visits"])}</td></tr>')
    stamp = datetime.fromisoformat(data['captured_at'].replace('Z', '+00:00')).astimezone(timezone.utc).strftime('%d %b %Y, %H:%M UTC') if data['captured_at'] else 'Not yet archived'
    current_visitors = f'{data["current_visitors"]:,}' if data['current_visitors'] is not None else '—'
    month_label = datetime.strptime(data['current_month'], '%Y-%m').strftime('%b %Y')
    current_note = 'Saved so far' if data['current_visitors'] is not None else 'Awaiting this month’s export'
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return f'''<section id="visitors" class="visitor-panel visitor-panel--umami" aria-labelledby="visitor-title">
  <div class="visitor-copy"><p class="eyebrow">Around the world · Umami</p><h2 id="visitor-title">A world of visitors.</h2>
    <div class="visitor-total"><strong>{total:,}</strong><span>Total archived visits</span></div>
    <div class="visitor-mini-stats"><div><strong id="visitor-current-count">{current_visitors}</strong><span>Visitors · <span id="visitor-current-month">{month_label}</span></span><small id="visitor-current-note">{current_note}</small></div><div><strong>{known}</strong><span>Countries / regions</span><small>Across archived months</small></div></div>
    <p class="visitor-note">Since {esc(data['tracking_started'])}<br>Archived through {stamp}.<br>Monthly snapshots, updated after import.</p>
  </div>
  <div class="visitor-map-card">
    <div class="visitor-map-heading"><span>Where visits come from</span><span>{known} countries / regions</span></div>
    <svg class="visitor-world" viewBox="0 0 720 310" role="group" aria-label="World map of archived Umami visits by country or region" aria-describedby="visitor-map-note">
      <image href="/images/visitor-world.svg" width="720" height="310" aria-hidden="true"/>
      {''.join(markers)}
    </svg>
    <p id="visitor-map-note" class="visitor-map-note">Select a marker or country to explore. Markers show country/region reference points, not precise visitor locations.</p>
    <div class="visitor-location-toolbar"><label for="visitor-country">Country / region</label><select id="visitor-country"><option value="all">All locations</option>{''.join(options)}</select></div>
    <div id="visitor-location-detail" aria-live="polite"><p class="visitor-detail-title">Leading locations · share of all {total:,} archived visits</p><table class="visitor-location-table"><thead><tr><th scope="col">Location</th><th scope="col">Visits</th><th scope="col">Share</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
    <p class="visitor-map-note">{unmapped:,} visits without a map position remain included in totals. Coverage: {esc(', '.join(data['months']) or 'no archived months')}. Setup / VPN test visits are included.</p>
    <p class="visitor-map-credit">Map: <a href="https://www.naturalearthdata.com/">Natural Earth</a> · Reference points: <a href="https://developers.google.com/public-data/docs/canonical/countries_csv">Google DSPL</a></p>
  </div>
  <script type="application/json" id="visitor-map-data">{encoded}</script>
</section>'''
