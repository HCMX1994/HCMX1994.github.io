"""Verify the complete generated website and preservation of source collections."""
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.images = []
        self.h1 = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'h1':
            self.h1 += 1
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'img':
            self.images.append(attrs)
        if tag in ['script', 'link']:
            if tag == 'link' and attrs.get('rel') == 'canonical':
                return
            src = attrs.get('src') or attrs.get('href')
            if src:
                self.links.append(src)

def target_file(path):
    candidate = OUT / unquote(path).lstrip('/')
    return candidate if candidate.suffix else candidate / 'index.html'

def main():
    manifest = json.loads((ROOT / 'tmp/site-manifest.json').read_text(encoding='utf-8'))
    pages = {}
    failures = []
    for file in OUT.rglob('*.html'):
        page = Page()
        text = file.read_text(encoding='utf-8')
        page.feed(text)
        pages[file.resolve()] = page
        if '{{' in text or '{%' in text:
            failures.append(f'Unresolved template: {file}')
    checked = 0
    if 'publications' in manifest['collections']:
        failures.append('Publication records should be maintained on Google Scholar')
    if any(file != OUT / 'publications/index.html' for file in (OUT / 'publications').rglob('*.html')):
        failures.append('Retired publication detail pages remain in the output')
    for entry in manifest['pages']:
        file = target_file(entry['url']).resolve()
        if file not in pages:
            failures.append('Missing page: ' + entry['url'])
            continue
        page = pages[file]
        if page.h1 != 1:
            failures.append(f'Expected one H1: {entry["url"]} ({page.h1})')
        for image in page.images:
            if not image.get('alt'):
                failures.append('Image without alternative text: ' + entry['url'])
        for href in page.links + [i.get('src', '') for i in page.images]:
            parsed = urlsplit(href)
            if parsed.hostname and parsed.hostname.lower() == 'hcmx1994.github.io':
                failures.append(f'Hardcoded old-site link: {entry["url"]} -> {href}')
            if parsed.scheme or parsed.netloc or not href:
                continue
            full = urlsplit(urljoin(entry['url'], href))
            dest = target_file(full.path).resolve()
            checked += 1
            if not dest.is_relative_to(OUT.resolve()) or not dest.is_file():
                failures.append(f'Broken internal link: {entry["url"]} -> {href}')
            elif full.fragment and dest in pages and unquote(full.fragment) not in pages[dest].ids:
                failures.append(f'Missing section: {entry["url"]} -> {href}')
    for collection, items in manifest['collections'].items():
        sources = {p.relative_to(ROOT).as_posix() for p in (ROOT / ('_' + collection)).glob('*.md')}
        migrated = {i['source'] for i in items}
        if sources != migrated:
            failures.append(f'Source collection incomplete: {collection}')
        for item in items:
            if not target_file(item['url']).is_file():
                failures.append(f'Unbuilt record: {item["source"]}')
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f'PASS: {len(manifest["pages"])} pages, {checked} internal links/assets, all selected collections built, no old-site links or standalone publication records.')

if __name__ == '__main__':
    main()
