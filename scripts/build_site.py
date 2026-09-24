"""Build the complete site from the existing Markdown collections.

This public output is used by GitHub Pages and the preview server.
The loopback preview may inject owner notes separately; they never enter _site.
Only explicitly selected public content/assets are copied to _site.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
HOME_CSS = ROOT / 'assets/css/academic-home.css'
HOME_CSS_NAME = f'academic-home.{hashlib.sha256(HOME_CSS.read_bytes()).hexdigest()[:12]}.css'
BD_JS = ROOT / 'assets/js/bd-ris-demo.js'
BD_JS_NAME = f'bd-ris-demo.{hashlib.sha256(BD_JS.read_bytes()).hexdigest()[:12]}.js'
BD_MODEL_JS = ROOT / 'assets/js/bd-ris-model.js'
BD_MODEL_JS_NAME = f'bd-ris-model.{hashlib.sha256(BD_MODEL_JS.read_bytes()).hexdigest()[:12]}.js'
STATS_JS = ROOT / 'assets/js/profile-stats.js'
STATS_JS_NAME = f'profile-stats.{hashlib.sha256(STATS_JS.read_bytes()).hexdigest()[:12]}.js'
sys.path.insert(0, str(ROOT / '.build-deps'))
import markdown
import yaml

OUT = ROOT / '_site'
ORIGIN = 'https://hcmx1994.github.io'
SCHOLAR_URL = 'https://scholar.google.com/citations?user=vj_3bhQAAAAJ&hl=en'
PUBLIC_ROOT_FILES = ('85d24de9d58fae23945a5d596cb929cc.txt',)
HOME_DESCRIPTION = ('Xuekang Liu, Lecturer (Assistant Professor) at Lancaster University. '
                    'Research in antennas, reconfigurable circuits, metasurfaces and sub-THz communications.')
COLLECTIONS = {'posts': ('News & milestones', '/year-archive/'),
               'portfolio': ('Research portfolio', '/portfolio/'),
               'teaching': ('Teaching', '/teaching/')}

def escape(value):
    return html.escape(str(value), quote=True)

def internal_links(text):
    return re.sub(r'https?://hcmx1994\.github\.io(?=[/\s\"\'<>]|$)', '', text, flags=re.I)

def read_item(file, collection):
    text = file.read_text(encoding='utf-8-sig')
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', text, re.S)
    if not match:
        raise ValueError(f'Missing front matter: {file.name}')
    meta = yaml.safe_load(match[1]) or {}
    body = internal_links(match[2].strip())
    original = str(meta.get('permalink') or '')
    # Preserve original local routes for the published collections.
    local = original if original.startswith('/') and not original.startswith('//') else f'/{collection}/{file.stem}/'
    if not local.endswith('/') and not Path(local).suffix:
        local += '/'
    return {**meta, 'body': body, 'url': local, 'collection': collection,
            'source': file.relative_to(ROOT).as_posix(), 'publisher': original if original.startswith('https://') else None}

def date_label(value):
    if not value:
        return ''
    raw = str(value)
    if re.fullmatch(r'\d{4}', raw):
        return raw
    if re.fullmatch(r'\d{4}-\d{2}', raw):
        return date.fromisoformat(raw + '-01').strftime('%B %Y')
    return date.fromisoformat(raw[:10]).strftime('%d %B %Y').lstrip('0')

def plain_excerpt(item):
    text = str(item.get('excerpt') or item['body'].split('\n\n')[0])
    text = markdown.markdown(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\s+', ' ', html.unescape(text)).strip()
    return text if len(text) <= 280 else text[:277].rsplit(' ', 1)[0] + '…'

def render_markdown(item):
    text = markdown.markdown(item['body'], extensions=['extra', 'sane_lists', 'smarty'])
    # Original content headings begin at H1. Reserve H1 for the page title.
    text = re.sub(r'<(/?)h([1-5])\b', lambda m: f'<{m[1]}h{int(m[2])+1}', text)
    # Original image references remain local; supply accessible descriptions.
    def image_tag(match):
        tag = match[0]
        if not re.search(r'\balt=', tag):
            tag = tag[:-1] + f' alt="{escape(item["title"])}" loading="lazy">'
        return tag
    return re.sub(r'<img\b[^>]*>', image_tag, text)

def write_route(route, content):
    path = OUT / route.lstrip('/')
    if not Path(route).suffix:
        path /= 'index.html'
    if not path.resolve().is_relative_to(OUT.resolve()):
        raise ValueError('Output path leaves _site')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

def render_layout(content, title, route, description=''):
    layout = (ROOT / '_layouts/academic-home.html').read_text(encoding='utf-8-sig')
    seo_title = 'Xuekang Liu | Lecturer at Lancaster University' if route == '/' else f'{title} | Xuekang Liu'
    layout = layout.replace('{{ page.title }} | {{ site.name }}', escape(seo_title))
    layout = layout.replace('{{ content }}', content)
    layout = layout.replace('{{ page.title }}', escape(title)).replace('{{ site.name }}', 'Xuekang Liu')
    layout = layout.replace("{{ page.url | absolute_url }}", ORIGIN + route)
    layout = re.sub(r"{{ '([^']+)' \| relative_url }}", r'\1', layout)
    # A new stylesheet filename prevents returning visitors from using stale CSS.
    layout = layout.replace('href="/assets/css/academic-home.css"',
                            f'href="/assets/css/{HOME_CSS_NAME}"')
    layout = layout.replace('src="/assets/js/bd-ris-demo.js"',
                            f'src="/assets/js/{BD_JS_NAME}"')
    layout = layout.replace('src="/assets/js/bd-ris-model.js"',
                            f'src="/assets/js/{BD_MODEL_JS_NAME}"')
    layout = layout.replace('src="/assets/js/profile-stats.js"',
                            f'src="/assets/js/{STATS_JS_NAME}"')
    if description:
        layout = re.sub(r'<meta name="description" content="[^"]*">', '<meta name="description" content="' + escape(description) + '">', layout)
    page_description = description or HOME_DESCRIPTION
    metadata = [
        '<meta name="author" content="Xuekang Liu">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="Xuekang Liu">',
        f'<meta property="og:title" content="{escape(seo_title)}">',
        f'<meta property="og:description" content="{escape(page_description)}">',
        f'<meta property="og:url" content="{escape(ORIGIN + route)}">',
        f'<meta property="og:image" content="{ORIGIN}/images/XuekangPhoto.png">',
        '<meta property="og:image:alt" content="Xuekang Liu">',
    ]
    if route == '/':
        person = {
            '@type': 'Person', '@id': ORIGIN + '/#person',
            'name': 'Xuekang Liu', 'url': ORIGIN + '/',
            'image': ORIGIN + '/images/XuekangPhoto.png',
            'jobTitle': 'Lecturer (Assistant Professor) in Electronics and Communication Engineering',
            'worksFor': {'@type': 'CollegeOrUniversity', 'name': 'Lancaster University',
                         'url': 'https://www.lancaster.ac.uk/'},
            'alumniOf': [{'@type': 'CollegeOrUniversity', 'name': 'University of Kent'},
                        {'@type': 'CollegeOrUniversity', 'name': 'Xidian University'}],
            'sameAs': [SCHOLAR_URL, 'https://orcid.org/0000-0002-3318-6812',
                       'https://www.linkedin.com/in/xuekang-liu-7a383a1b0/',
                       'https://www.researchgate.net/profile/Xuekang-Liu'],
        }
        structured = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'WebSite', '@id': ORIGIN + '/#website',
             'url': ORIGIN + '/', 'name': 'Xuekang Liu'},
            {'@type': 'ProfilePage', '@id': ORIGIN + '/#profile',
             'url': ORIGIN + '/', 'name': seo_title, 'mainEntity': person},
        ]}
        metadata.append('<script type="application/ld+json">' +
                        json.dumps(structured, ensure_ascii=False).replace('<', '\\u003c') + '</script>')
    if route == '/404.html':
        metadata.append('<meta name="robots" content="noindex">')
    layout = layout.replace('</head>', '  ' + '\n  '.join(metadata) + '\n</head>')
    if '{{' in layout or '{%' in layout:
        raise ValueError('Unresolved template in ' + route)
    return layout

def main():
    OUT.mkdir(exist_ok=True)
    # Rebuild the archive from its canonical aggregate data on every deployment.
    visitor_archive = ROOT / 'files/visitor-history.json'
    if visitor_archive.is_file():
        from archive_visitors import render as render_visitor_archive
        archive_data = json.loads(visitor_archive.read_text(encoding='utf-8'))
        visitor_archive.with_suffix('.html').write_text(render_visitor_archive(archive_data), encoding='utf-8')
    # Publication records now live on Google Scholar. Remove only previously
    # generated HTML under this output directory; keep the source Markdown.
    retired = OUT / 'publications'
    if not OUT.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Output directory leaves the workspace')
    if retired.exists():
        if not retired.resolve().is_relative_to(OUT.resolve()):
            raise ValueError('Publication output leaves _site')
        for file in retired.rglob('*.html'):
            if not file.resolve().is_relative_to(retired.resolve()):
                raise ValueError('Publication output file leaves its directory')
            file.unlink()
    # Preserve the explicitly approved WeChat verification file on every deployment.
    for name in PUBLIC_ROOT_FILES:
        shutil.copy2(ROOT / name, OUT / name)
    # Copy public assets, never the input CV, scratch files or repository data.
    for dirname in ['images', 'files']:
        for file in (ROOT / dirname).rglob('*'):
            if file.is_file():
                target = OUT / file.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists() or file.stat().st_mtime_ns > target.stat().st_mtime_ns:
                    shutil.copy2(file, target)
    for dirname in ['assets/css', 'assets/data']:
        for file in (ROOT / dirname).glob('*'):
            if file.is_file() and file.suffix in ['.css', '.json']:
                target = OUT / file.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
    shutil.copy2(HOME_CSS, OUT / 'assets/css' / HOME_CSS_NAME)
    (OUT / 'assets/js').mkdir(parents=True, exist_ok=True)
    shutil.copy2(STATS_JS, OUT / 'assets/js' / STATS_JS_NAME)
    shutil.copy2(BD_JS, OUT / 'assets/js' / BD_JS_NAME)
    shutil.copy2(BD_MODEL_JS, OUT / 'assets/js' / BD_MODEL_JS_NAME)

    home = (ROOT / '_includes/academic-home.html').read_text(encoding='utf-8-sig')
    header = re.search(r'<header\b.*?</header>', home, re.S)[0]
    header = header.replace('href="#', 'href="/#')
    footer = re.search(r'<footer\b.*?</footer>', home, re.S)[0]
    pages = []
    def save(route, title, inner, description='', bare=False):
        content = inner if bare else header + '<main id="main" class="content-main">' + inner + '</main>' + footer
        write_route(route, render_layout(content, title, route, description))
        pages.append({'url': route, 'title': title})

    def page_head(title, eyebrow, description=''):
        return '<div class="page-intro"><p class="eyebrow">' + escape(eyebrow) + '</p><h1>' + escape(title) + '</h1>' + (f'<p class="page-description">{description}</p>' if description else '') + '</div>'

    all_items = {}
    for collection in COLLECTIONS:
        items = [read_item(file, collection) for file in sorted((ROOT / ('_' + collection)).glob('*.md'))]
        if collection != 'portfolio':
            items.sort(key=lambda i: str(i.get('date', '')), reverse=True)
        all_items[collection] = items

    save('/', 'Xuekang Liu — Lancaster University', home, HOME_DESCRIPTION, bare=True)

    for collection, items in all_items.items():
        label, listing = COLLECTIONS[collection]
        for item in items:
            intro = f'<a class="back-link" href="{listing}">← {label}</a>' + page_head(item['title'], label)
            metadata = []
            if item.get('date'):
                metadata.append(date_label(item['date']))
            if item.get('venue'):
                metadata.append(str(item['venue']))
            if metadata:
                intro += '<p class="entry-meta">' + ' · '.join(escape(m) for m in metadata) + '</p>'
            actions = []
            if item.get('publisher'):
                actions.append(f'<a class="button button-primary" href="{escape(item["publisher"])}">Publisher page ↗</a>')
            paper = str(item.get('paperurl') or '').strip()
            if paper and paper != item.get('publisher'):
                actions.append(f'<a class="text-link" href="{escape(paper)}">Read paper ↗</a>')
            content = intro + ('<div class="entry-actions">' + ''.join(actions) + '</div>' if actions else '')
            content += '<article class="article-body">' + render_markdown(item) + '</article>'
            content += f'<div class="entry-bottom"><a class="text-link" href="{listing}">← Back to {label.lower()}</a></div>'
            save(item['url'], item['title'], content, plain_excerpt(item))

        if collection == 'posts':
            content = page_head(label, 'Academic life', 'Research updates, awards and milestones through the years.')
            year = None
            for item in items:
                next_year = str(item['date'])[:4]
                if year != next_year:
                    if year is not None:
                        content += '</div>'
                    year = next_year
                    content += f'<div class="archive-year" id="year-{year}"><h2>{year}</h2>'
                content += f'<article class="archive-entry"><p class="entry-meta">{escape(date_label(item["date"]))}</p><h3><a href="{item["url"]}">{escape(item["title"])} →</a></h3><p>{escape(plain_excerpt(item))}</p><a class="text-link" href="{item["url"]}">Read update →</a></article>'
            content += '</div>'
        elif collection == 'portfolio':
            content = page_head(label, 'Design & experimentation', 'A gallery of antenna arrays, transmitarrays and fabricated research prototypes.') + '<div class="portfolio-grid">'
            for item in items:
                image = re.search(r'<img[^>]*src=[\"\']([^\"\']+)', item['body'])
                photo = f'<img src="{escape(image[1])}" alt="{escape(item["title"])}" loading="lazy">' if image else ''
                content += f'<article class="portfolio-card"><a href="{item["url"]}"><div class="portfolio-photo">{photo}</div><h2>{escape(item["title"])} <span aria-hidden="true">→</span></h2></a></article>'
            content += '</div>'
        else:
            description = 'Past teaching as a Sessional Demonstrator at the University of Kent (2021–2022), in the years indicated below.'
            content = page_head(label, 'Past teaching experience', description)
            for item in items:
                meta = date_label(item.get('date')) + (' · ' + str(item['venue']) if item.get('venue') else '')
                content += f'<article class="archive-entry"><p class="entry-meta">{escape(meta)}</p><h2><a href="{item["url"]}">{escape(item["title"])}</a></h2><p>{escape(plain_excerpt(item))}</p><a class="text-link" href="{item["url"]}">Read course details</a></article>'
        save(listing, label, content)

    # Keep old About and news URLs, and send the former publication index to Scholar.
    for alias, target in {'/about/':'/', '/about.html':'/', '/news/':'/year-archive/', '/wordpress/blog-posts/':'/year-archive/', '/publications/':SCHOLAR_URL}.items():
        write_route(alias, '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=' + escape(target) + '"><title>Page moved</title></head><body><a href="' + escape(target) + '">Continue to the page</a></body></html>')

    # Replace sample CV content with the owner's actual site profile.
    experience = re.search(r'<section id="experience".*?</section>', home, re.S)[0]
    save('/cv/', 'Academic profile', page_head('Academic profile', 'Xuekang Liu', 'Lecturer (Assistant Professor) in Electronics and Communication Engineering, Lancaster University.') + experience)
    sitemap_body = page_head('Sitemap', 'Explore the website') + '<ul class="sitemap-list">' + ''.join(f'<li><a href="{p["url"]}">{escape(p["title"])}</a></li>' for p in pages) + '</ul>'
    save('/sitemap/', 'Sitemap', sitemap_body)
    write_route('/404.html', render_layout(header + '<main id="main" class="content-main">' + page_head('Page not found', '404', 'The page may have moved. Explore the news, publications or portfolio using the navigation above.') + '<a class="button button-primary" href="/">Back to home</a></main>' + footer, 'Page not found', '/404.html'))
    (OUT / '.nojekyll').write_text('', encoding='utf-8')
    (OUT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>' + escape(ORIGIN+p['url']) + '</loc></url>' for p in pages) + '</urlset>', encoding='utf-8')
    (OUT / 'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: ' + ORIGIN + '/sitemap.xml\n', encoding='utf-8')
    # A machine-readable manifest lets validation prove every source migrated.
    manifest = {'pages': pages, 'collections': {key: [{'source': i['source'], 'url': i['url'], 'title': i['title']} for i in value] for key, value in all_items.items()}}
    (ROOT / 'tmp').mkdir(exist_ok=True)
    (ROOT / 'tmp/site-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Built {len(pages)} pages: ' + ', '.join(f'{len(items)} {key}' for key, items in all_items.items()))

if __name__ == '__main__':
    main()
