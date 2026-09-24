"""Archive complete monthly Umami geography CSVs without using a paid API.

Run --help for the import command. Only aggregate metrics are accepted/published.
The same month is replaced, never appended; other months remain untouched.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import gzip
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
WEBSITE_ID = '3000b10a-b4af-481b-ac2b-a6a611908de4'
DOMAIN = 'hcmx1994.github.io'
ARCHIVE = ROOT / 'files/visitor-history.json'
METRICS = ('visitors', 'visits', 'pageviews')


def count(value):
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value).strip()):
        raise ValueError(f'Expected a non-negative whole count, got {value!r}')
    return int(value)


def validate_metrics(values):
    values = {key: count(values[key]) for key in METRICS}
    if not values['visitors'] <= values['visits'] <= values['pageviews']:
        raise ValueError('Expected visitors <= visits <= pageviews')
    return values


def read_export(path, dimension):
    raw = Path(path).read_bytes()
    data = gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    required = {'name', *METRICS} | ({'country'} if dimension == 'cities' else set())
    if not required.issubset(reader.fieldnames or []):
        raise ValueError(f'{path}: use the complete Umami Country/City detail-table CSV export; missing {required - set(reader.fieldnames or [])}')
    result, seen = [], set()
    for raw_row in reader:
        name = (raw_row.get('name') or '').strip()
        code = (raw_row.get('country') if dimension == 'cities' else name) or ''
        code = code.strip().upper()
        if code.lower() in ('unknown', '(unknown)', 'null', 'undefined'):
            code = ''
        if code and not re.fullmatch(r'[A-Z]{2}', code):
            raise ValueError(f'Invalid country code: {code!r}')
        if dimension == 'countries':
            name = code
        elif name.lower() in ('unknown', '(unknown)', 'null', 'undefined'):
            name = ''
        if len(name) > 160 or any(ord(char) < 32 for char in name):
            raise ValueError('Invalid location label')
        key = (code, name)
        if key in seen:
            raise ValueError(f'Duplicate location in export: {key}')
        seen.add(key)
        result.append({'country': code or None, 'city': name or None if dimension == 'cities' else None,
                       **validate_metrics(raw_row)})
    return result, hashlib.sha256(raw).hexdigest()


def new_archive():
    return {'schema_version': 1, 'source': 'Umami', 'website_id': WEBSITE_ID,
            'domain': DOMAIN, 'tracking_started': '2026-09-24',
            'distribution_basis': 'visits', 'months': []}


def validate_archive(archive):
    if (archive.get('schema_version') != 1 or archive.get('source') != 'Umami'
            or archive.get('website_id') != WEBSITE_ID or archive.get('domain') != DOMAIN
            or archive.get('distribution_basis') != 'visits'):
        raise ValueError('Wrong archive format or website')
    seen, zones = set(), set()
    for month in archive['months']:
        key = month['month']
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', key) or key in seen:
            raise ValueError('Invalid or duplicate calendar month')
        seen.add(key)
        zones.add(month['timezone'])
        ZoneInfo(month['timezone'])
        stamp = datetime.fromisoformat(month['captured_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None or not isinstance(month['complete'], bool):
            raise ValueError('Archive capture must have a timezone and completion status')
        month_start = datetime.fromisoformat(key + '-01').date()
        if month_start > stamp.astimezone(ZoneInfo(month['timezone'])).date():
            raise ValueError('Cannot archive a future month')
        year, number = map(int, key.split('-'))
        final_day = month_start.replace(day=calendar.monthrange(year, number)[1])
        if month['complete'] and stamp.astimezone(ZoneInfo(month['timezone'])).date() <= final_day:
            raise ValueError('The current month cannot be marked complete')
        totals = validate_metrics(month['totals'])
        for dimension in ('countries', 'cities'):
            locations = set()
            for row in month[dimension]:
                validate_metrics(row)
                code = row['country']
                if code is not None and not re.fullmatch(r'[A-Z]{2}', code):
                    raise ValueError('Invalid country in archive')
                location = (code, row['city'] if dimension == 'cities' else None)
                if location in locations:
                    raise ValueError('Duplicate archived location')
                locations.add(location)
            for metric in ('visits', 'pageviews'):
                if sum(row[metric] for row in month[dimension]) != totals[metric]:
                    raise ValueError(f'{key} {dimension}: {metric} do not match overview totals. Export ALL rows for the same unfiltered month; do not use the top-ten card.')
        for metric in ('visits', 'pageviews'):
            by_country = defaultdict(int)
            for row in month['cities']:
                by_country[row['country']] += row[metric]
            expected = {row['country']: row[metric] for row in month['countries']}
            if dict(by_country) != expected:
                raise ValueError(f'{key}: city and country {metric} disagree; re-export both together')
    if len(zones) > 1:
        raise ValueError('All archive months must use the same timezone')


def import_month(archive, month, allow_correction=False):
    archive = json.loads(json.dumps(archive))
    existing = next((row for row in archive['months'] if row['month'] == month['month']), None)
    if existing:
        if datetime.fromisoformat(month['captured_at'].replace('Z', '+00:00')) < datetime.fromisoformat(existing['captured_at'].replace('Z', '+00:00')):
            raise ValueError('Cannot replace a newer snapshot with an older one')
        if existing['complete'] and not month['complete']:
            raise ValueError('Cannot replace a complete month with a partial month')
        if not allow_correction and any(month['totals'][key] < existing['totals'][key] for key in METRICS):
            raise ValueError('Counts decreased. Verify the export; use --allow-correction only for a verified provider correction.')
    archive['months'] = sorted([row for row in archive['months'] if row['month'] != month['month']] + [month], key=lambda row: row['month'])
    validate_archive(archive)
    return archive


def render(archive):
    validate_archive(archive)
    data = json.dumps(archive, ensure_ascii=False).replace('<', '\\u003c')
    return PAGE.replace('__ARCHIVE_DATA__', data)


PAGE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Visitor history · Xuekang Liu</title>
<style>
:root{color-scheme:light;--ink:#183c47;--muted:#5c6b70;--line:#dce3e2;--paper:#faf9f6}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:44px 28px 70px}a{color:#245d76;text-underline-offset:4px}header{border-bottom:1px solid var(--line);padding-bottom:28px}header p{max-width:760px;color:var(--muted)}.eyebrow{text-transform:uppercase;font-size:12px;font-weight:700;letter-spacing:.14em}h1{font:clamp(35px,6vw,60px)/1.15 Georgia,serif;letter-spacing:-.03em;margin:15px 0}h2{font:28px/1.3 Georgia,serif;margin:0 0 16px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:28px 0}.stat{background:white;padding:22px}.stat strong{display:block;font-size:30px;font-weight:600}.stat span{font-size:13px;color:var(--muted)}.controls{display:flex;gap:18px;flex-wrap:wrap;align-items:center;justify-content:space-between;margin:30px 0 18px}label{font-size:14px}select,input{font:inherit;border:1px solid #9baead;border-radius:4px;padding:8px;background:white;color:var(--ink);max-width:100%}.switch{display:flex;gap:6px}.switch button{font:inherit;padding:8px 14px;border:1px solid #9baead;border-radius:4px;background:transparent;color:var(--ink);cursor:pointer}.switch button[aria-pressed=true]{background:var(--ink);color:white}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:12px 10px;border-bottom:1px solid var(--line)}th{font-weight:600;color:var(--muted);white-space:nowrap}.number{text-align:right;font-variant-numeric:tabular-nums}.distribution{display:grid;grid-template-columns:minmax(0,1fr) 180px;gap:30px;align-items:start}.distribution table{background:white;border:1px solid var(--line)}.bar{height:4px;background:#ebeeee;border-radius:2px;margin-top:6px;width:100%;min-width:65px}.bar span{height:100%;display:block;background:#327a81;border-radius:2px}.note{font-size:13px;color:var(--muted)}.status{padding:12px 16px;border-left:3px solid #b98945;background:#f5eee1;color:#665230;margin-top:18px}.periods{margin-top:45px}.table-scroll{overflow-x:auto}.footer{margin-top:35px;border-top:1px solid var(--line);padding-top:20px}button:focus-visible,a:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #c29b54;outline-offset:3px}@media(max-width:640px){main{padding:26px 18px 45px}.stats{grid-template-columns:repeat(2,1fr)}.stat{padding:16px}.distribution{grid-template-columns:1fr}.controls{align-items:flex-start;flex-direction:column}.number{padding-left:5px;padding-right:5px}.distribution aside{order:-1}.distribution aside p{margin:0 0 6px}}
</style></head><body><main>
<header><a href="/">← Xuekang Liu</a><p class="eyebrow">A record through the years</p><h1>Visitor history.</h1><p>Archived visits and geographic distribution, kept independently of the analytics provider’s retention window.</p><p id="updated" class="note"></p></header>
<noscript>This archive viewer requires JavaScript. The complete saved data is available in <a href="visitor-history.json">JSON format</a>.</noscript>
<div class="controls"><label>Period <select id="period"><option value="all">All archived months</option></select></label><a href="visitor-history.json" download>Download saved data ↓</a></div>
<div class="stats" aria-live="polite"><div class="stat"><strong id="visits">—</strong><span>Recorded visits</span></div><div class="stat"><strong id="views">—</strong><span>Page views</span></div><div class="stat"><strong id="countries">—</strong><span>Countries / regions</span></div><div class="stat"><strong id="cities">—</strong><span>Identified cities</span></div></div>
<div id="coverage" class="note"></div><div id="partial" class="status" hidden></div>
<section aria-labelledby="location-title"><div class="controls"><h2 id="location-title">Where visits came from</h2><div class="switch" aria-label="Geographic detail"><button type="button" id="country-button" aria-pressed="true">Countries / regions</button><button type="button" id="city-button" aria-pressed="false">Cities</button></div></div>
<div class="distribution"><div><label>Find a location <input id="search" type="search" placeholder="Country or city"></label><p id="result-count" class="note" aria-live="polite"></p><table><thead><tr><th scope="col">Location</th><th scope="col" class="number">Visits</th><th scope="col" class="number">Share</th></tr></thead><tbody id="locations"></tbody></table></div><aside class="note"><p><strong>How shares are calculated</strong></p><p>Location visits ÷ all recorded visits in the selected period. Unknown locations remain included in the denominator.</p><p>Searching the table does not change the denominator.</p><p>Locations are approximate IP-based estimates supplied by Umami.</p></aside></div></section>
<section class="periods" aria-labelledby="period-title"><h2 id="period-title">Monthly records</h2><div class="table-scroll"><table><thead><tr><th scope="col">Month</th><th scope="col" class="number">Visitors*</th><th scope="col" class="number">Visits</th><th scope="col" class="number">Page views</th><th scope="col">Snapshot</th></tr></thead><tbody id="months"></tbody></table></div><p class="note">* Visitor counts retain Umami’s count for each month. Returning visitors may appear in several months, so monthly visitors are not added together as an all-time unique-person count. Visits and page views are additive across the non-overlapping months.</p></section>
<div class="footer note"><p>Source: Umami only · Recording began 24 September 2026. These are manually imported snapshots, not a live counter. Only archived Umami data is included. Setup and VPN test visits are included.</p><p><a href="/">Back to the homepage</a></p></div>
</main><script type="application/json" id="archive-data">__ARCHIVE_DATA__</script><script>
'use strict';
const archive=JSON.parse(document.getElementById('archive-data').textContent), months=archive.months;
const number=new Intl.NumberFormat('en-GB'), regions=new Intl.DisplayNames(['en'],{type:'region'});
const get=id=>document.getElementById(id);let dimension='countries';
const country=code=>code?regions.of(code):'Unknown country';
const date=value=>new Date(value).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:'UTC'})+' UTC';
const sum=(rows,key)=>rows.reduce((n,row)=>n+row[key],0);
const addCell=(row,text,cls)=>{const cell=document.createElement('td');cell.textContent=text;if(cls)cell.className=cls;row.append(cell);return cell;};
for(const month of [...months].reverse()){const option=document.createElement('option');option.value=month.month;option.textContent=month.month;get('period').append(option);const row=document.createElement('tr');addCell(row,month.month);for(const key of ['visitors','visits','pageviews'])addCell(row,number.format(month.totals[key]),'number');addCell(row,(month.complete?'Complete':'Partial')+' · '+date(month.captured_at));get('months').append(row);}
get('updated').textContent=months.length?'Last archived '+date([...months].map(m=>m.captured_at).sort().at(-1))+' · '+months[0].timezone+' calendar months':'No statistics have been archived yet.';
function aggregate(selected,field){const rows=new Map();for(const month of selected)for(const row of month[field]){const key=JSON.stringify([row.country,field==='cities'?row.city:null]);if(!rows.has(key))rows.set(key,{country:row.country,city:row.city,visits:0,pageviews:0});const target=rows.get(key);target.visits+=row.visits;target.pageviews+=row.pageviews;}return [...rows.values()].sort((a,b)=>b.visits-a.visits||(a.city||a.country||'').localeCompare(b.city||b.country||''));}
function render(){const selected=months.filter(m=>get('period').value==='all'||m.month===get('period').value), total=sum(selected.map(m=>m.totals),'visits');const countries=aggregate(selected,'countries'),cities=aggregate(selected,'cities');get('visits').textContent=number.format(total);get('views').textContent=number.format(sum(selected.map(m=>m.totals),'pageviews'));get('countries').textContent=number.format(countries.filter(r=>r.country&&r.visits).length);get('cities').textContent=number.format(cities.filter(r=>r.city&&r.visits).length);get('coverage').textContent='Archived months: '+(selected.map(m=>m.month).join(', ')||'none')+'. Unlisted months are not included; missing data is not treated as zero.';const partial=selected.filter(m=>!m.complete);get('partial').hidden=!partial.length;get('partial').textContent='Partial months: '+partial.map(m=>m.month+' (through '+date(m.captured_at)+')').join('; ')+'. Import an updated export to complete these months.';const search=get('search').value.toLocaleLowerCase(), rows=(dimension==='cities'?cities:countries).map(r=>({...r,label:dimension==='cities'?(r.city||'Unknown city')+', '+country(r.country):country(r.country)}));const filtered=rows.filter(r=>r.label.toLocaleLowerCase().includes(search));get('locations').replaceChildren();for(const item of filtered){const row=document.createElement('tr');addCell(row,item.label);addCell(row,number.format(item.visits),'number');const pct=total?100*item.visits/total:0,cell=addCell(row,pct.toFixed(1)+'%','number'),bar=document.createElement('div'),fill=document.createElement('span');bar.className='bar';bar.setAttribute('aria-hidden','true');fill.style.width=pct+'%';bar.append(fill);cell.append(bar);get('locations').append(row);}if(!filtered.length){const row=document.createElement('tr'),cell=addCell(row,'No matching locations.');cell.colSpan=3;get('locations').append(row);}get('result-count').textContent=filtered.length+' of '+rows.length+' locations · shares of '+number.format(total)+' visits';}
get('period').addEventListener('change',render);get('search').addEventListener('input',render);for(const [id,field] of [['country-button','countries'],['city-button','cities']])get(id).addEventListener('click',()=>{dimension=field;get('country-button').setAttribute('aria-pressed',String(field==='countries'));get('city-button').setAttribute('aria-pressed',String(field==='cities'));render();});render();
</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--month', help='Calendar month YYYY-MM; use the same timezone in Umami')
    parser.add_argument('--countries', type=Path, help='Country detail-table CSV (all rows)')
    parser.add_argument('--cities', type=Path, help='City detail-table CSV (all rows)')
    parser.add_argument('--visitors', type=int, help='Visitors shown in the unfiltered monthly overview')
    parser.add_argument('--visits', type=int, help='Visits shown in the unfiltered monthly overview')
    parser.add_argument('--pageviews', type=int, help='Views shown in the unfiltered monthly overview')
    parser.add_argument('--timezone', default='Europe/London')
    parser.add_argument('--captured-at', default=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    parser.add_argument('--complete', action='store_true', help='Only for a finished calendar month')
    parser.add_argument('--allow-correction', action='store_true')
    parser.add_argument('--render-only', action='store_true')
    args = parser.parse_args()
    archive = json.loads(ARCHIVE.read_text(encoding='utf-8')) if ARCHIVE.exists() else new_archive()
    validate_archive(archive)
    if not args.render_only:
        if not all([args.month, args.countries, args.cities]) or any(getattr(args,key) is None for key in METRICS):
            parser.error('Import requires --month, both CSVs, --visitors, --visits and --pageviews')
        countries, country_hash = read_export(args.countries,'countries')
        cities, city_hash = read_export(args.cities,'cities')
        captured = datetime.fromisoformat(args.captured_at.replace('Z','+00:00'))
        if captured.tzinfo is None:
            raise ValueError('--captured-at must include a timezone')
        month = {'month':args.month, 'timezone':args.timezone,
                 'captured_at':captured.astimezone(timezone.utc).isoformat().replace('+00:00','Z'),
                 'complete':args.complete, 'totals':{key:getattr(args,key) for key in METRICS},
                 'countries':countries,'cities':cities,
                 'source_sha256':{'country_csv':country_hash,'city_csv':city_hash}}
        archive = import_month(archive,month,args.allow_correction)
    document = render(archive)
    serialized = json.dumps(archive, ensure_ascii=False, indent=2)+'\n'
    # Validate/render everything before replacing the canonical archive. Keep a
    # local recovery copy; Git commits preserve published historical revisions.
    if ARCHIVE.exists() and ARCHIVE.read_text(encoding='utf-8') != serialized:
        backup = ROOT / 'local/visitor-archive/backups'
        backup.mkdir(parents=True,exist_ok=True)
        digest=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()[:16]
        (backup / f'visitor-history-{digest}.json').write_bytes(ARCHIVE.read_bytes())
    ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
    temp = ARCHIVE.with_suffix('.json.tmp')
    temp.write_text(serialized,encoding='utf-8');temp.replace(ARCHIVE)
    output = ARCHIVE.with_suffix('.html');temp = output.with_suffix('.html.tmp')
    temp.write_text(document,encoding='utf-8');temp.replace(output)
    if not args.render_only:
        backup = ROOT / 'local/visitor-archive/exports' / args.month
        backup.mkdir(parents=True,exist_ok=True)
        for source,label in [(args.countries,'country'),(args.cities,'city')]:
            raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest()[:16]
            suffix='.csv.gz' if raw[:2]==b'\x1f\x8b' else '.csv'
            (backup / f'{label}-{digest}{suffix}').write_bytes(raw)
    print(f'Archived {len(archive["months"])} month(s); {sum(m["totals"]["visits"] for m in archive["months"])} visits. Public output: {output}')


if __name__ == '__main__':
    main()
