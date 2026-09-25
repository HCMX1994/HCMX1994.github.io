"""Read the public WoS profile once daily; preserve the snapshot on failure.

Only the aggregate verified-review count is stored. No sign-in, private API,
saved cookies, or review-level records are used.
"""
import json
import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

RESEARCHER_ID = 'GLN-3431-2022'
PROFILE_URL = f'https://www.webofscience.com/wos/author/record/{RESEARCHER_ID}'
OUTPUT = Path(__file__).resolve().parents[1] / 'assets/data/wos.json'


def parse_observation(observation):
    """Require the requested profile and the exact metric, not a nearby count."""
    url = urlsplit(observation['url'])
    if url.hostname != 'www.webofscience.com' or url.path.rstrip('/') != urlsplit(PROFILE_URL).path:
        raise ValueError('Unexpected profile URL')
    if RESEARCHER_ID not in observation['identity'] or not re.search(r'Xuekang\s+Liu', observation['name']):
        raise ValueError('Unexpected researcher')
    rows = observation['rows']
    if len(rows) != 1 or rows[0]['label'].strip() != 'Verified peer reviews':
        raise ValueError('Missing or ambiguous review count')
    value = rows[0]['count'].strip()
    if not re.fullmatch(r'\d+|\d{1,3}(?:,\d{3})+', value):
        raise ValueError('Review count is not a whole number')
    return int(value.replace(',', ''))


def validate_snapshot(data):
    if data['researcher_id'] != RESEARCHER_ID or data['source'] != PROFILE_URL:
        raise ValueError('Unexpected snapshot source')
    count = data['verified_peer_reviews']
    if type(count) is not int or count < 0:
        raise ValueError('Invalid review count')
    checked = datetime.fromisoformat(data['checked_at'].replace('Z', '+00:00'))
    if checked.tzinfo is None:
        raise ValueError('Verification time needs a timezone')
    if data['method'] not in ('public-profile-browser', 'public-profile-manual-check'):
        raise ValueError('Unknown verification method')
    return data


def fetch_count():
    # Import only when collecting: the website build and unit tests need no browser.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = None
        stage = 'open public profile'
        try:
            context = browser.new_context(locale='en-GB', timezone_id='UTC')
            page = context.new_page()
            response = page.goto(PROFILE_URL, wait_until='domcontentloaded', timeout=60000)
            if response is not None and response.status >= 400:
                raise ValueError(f'Public profile returned HTTP {response.status}')
            stage = 'wait for verified-review label'
            label = page.get_by_text('Verified peer reviews', exact=True)
            label.wait_for(state='visible', timeout=60000)
            rows = page.locator('p.summary-item').filter(has=label)
            observation = {
                'url': page.url,
                'name': ' '.join(page.get_by_role('heading', level=1).all_text_contents()),
                'identity': page.locator('body').inner_text(),
                'rows': rows.evaluate_all('''elements => elements.map(row => ({
                    label: row.querySelector('.summary-label')?.textContent || '',
                    count: row.querySelector('.summary-count')?.textContent || ''
                }))'''),
            }
            return parse_observation(observation)
        except Exception:
            # Public, signed-out page text helps distinguish loading failures from
            # access challenges. Never log cookies, network payloads or URL queries.
            diagnostic = {'stage': stage}
            if page is not None:
                try:
                    diagnostic['title'] = page.title()[:200]
                    text = page.locator('body').inner_text(timeout=5000)
                    diagnostic['visible_text'] = re.sub(r'https?://\S+', '[URL]', text)[:1600]
                except Exception:
                    diagnostic['visible_text'] = 'Page text unavailable'
            print('WoS public-page diagnostic: ' + json.dumps(diagnostic), file=sys.stderr)
            raise
        finally:
            browser.close()


def refresh(output=OUTPUT, fetch=fetch_count, now=None):
    now = now or datetime.now(timezone.utc)
    previous = None
    if output.exists():
        previous = validate_snapshot(json.loads(output.read_text(encoding='utf-8')))
        checked = datetime.fromisoformat(previous['checked_at'].replace('Z', '+00:00'))
        if previous['method'] == 'public-profile-browser' and checked.astimezone(timezone.utc).date() == now.date():
            print('WoS already verified today; keeping the daily snapshot.')
            return previous
    count = fetch()
    if type(count) is not int or count < 0:
        raise ValueError('Invalid review count')
    # A login/loading page must never silently reset a populated total to zero.
    if previous and previous['verified_peer_reviews'] > 0 and count == 0:
        raise ValueError('Unexpected zero; previous snapshot preserved')
    snapshot = validate_snapshot({
        'researcher_id': RESEARCHER_ID,
        'verified_peer_reviews': count,
        'checked_at': now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'source': PROFILE_URL,
        'method': 'public-profile-browser',
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(snapshot, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)
    print(f'WoS public profile verified: {count} peer reviews.')
    return snapshot


def render_panel(output=OUTPUT, now=None):
    """Render the saved value into HTML, including when JavaScript is disabled."""
    try:
        data = validate_snapshot(json.loads(output.read_text(encoding='utf-8')))
        checked = datetime.fromisoformat(data['checked_at'].replace('Z', '+00:00'))
        now = now or datetime.now(timezone.utc)
        pending = ' · Update pending' if (now - checked).total_seconds() > 3 * 86400 else ''
        label = checked.strftime('%d %b %Y').lstrip('0')
        return (f'<div class="review-metric" aria-label="Web of Science verified peer reviews">'
                f'<a class="review-metric-link" href="{PROFILE_URL}">'
                f'<strong>{data["verified_peer_reviews"]:,}</strong>'
                '<span>Verified peer reviews<span class="review-metric-source">Web of Science '
                '<span aria-hidden="true">↗</span></span></span></a>'
                f'<p>Last verified <time datetime="{escape(data["checked_at"])}">{label}</time>{pending}</p></div>')
    except (OSError, ValueError, KeyError, TypeError):
        return f'<p><a class="person-link" href="{PROFILE_URL}">View peer reviews on Web of Science ↗</a></p>'


def main():
    try:
        refresh()
        return 0
    except Exception as error:
        # Browser errors can include session URLs. Log only the error type.
        print(f'WoS refresh failed ({type(error).__name__}); previous count and verification date preserved.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
