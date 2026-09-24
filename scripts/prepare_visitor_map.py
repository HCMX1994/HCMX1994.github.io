"""Prepare an offline, non-tracking world basemap from public reference data.

Inputs: world-atlas@2.0.2/land-110m.json and Google's DSPL countries.csv page.
Run explicitly when updating reference geography, never during site builds.
"""
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CountryTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], [], None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        if tag == 'td':
            self.cell = ''

    def handle_data(self, text):
        if self.cell is not None:
            self.cell += text

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.row.append(self.cell.strip())
            self.cell = None
        if tag == 'tr' and len(self.row) == 4:
            self.rows.append(self.row)


def project(lon, lat):
    return (lon + 180) * 2, (90 - lat) * 2


def main():
    topology = json.loads((ROOT / 'tmp/land-110m.json').read_text())
    scale, translate = topology['transform']['scale'], topology['transform']['translate']
    arcs = []
    for arc in topology['arcs']:
        x = y = 0
        points = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append((x * scale[0] + translate[0], y * scale[1] + translate[1]))
        arcs.append(points)
    paths = []
    for geometry in topology['objects']['land']['geometries']:
        polygons = geometry['arcs'] if geometry['type'] == 'MultiPolygon' else [geometry['arcs']]
        for polygon in polygons:
            for ring in polygon:
                points = []
                for index in ring:
                    segment = arcs[index] if index >= 0 else list(reversed(arcs[~index]))
                    points.extend(segment if not points else segment[1:])
                if max(lat for lon, lat in points) < -60:
                    continue
                # Unwrap rings across +/-180 degrees before projection. Otherwise
                # Fiji and eastern Russia acquire lines across the entire map.
                unwrapped = []
                previous = points[0][0]
                for lon, lat in points:
                    while lon - previous > 180: lon -= 360
                    while lon - previous < -180: lon += 360
                    unwrapped.append((lon, lat))
                    previous = lon
                xy = [project(lon, lat) for lon, lat in unwrapped]
                for offset in (-720, 0, 720):
                    if max(x for x, y in xy) + offset < 0 or min(x for x, y in xy) + offset > 720:
                        continue
                    paths.append('M' + 'L'.join(f'{x+offset:.1f},{y:.1f}' for x, y in xy) + 'Z')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 310">'
           '<title>World land outline</title><desc>Natural Earth, via world-atlas 2.0.2. Equirectangular projection.</desc>'
           '<path fill="#dce5e2" stroke="#c5d2cd" stroke-width="0.6" d="' + ''.join(paths) + '"/></svg>')
    (ROOT / 'images/visitor-world.svg').write_text(svg, encoding='utf-8')
    table = CountryTable()
    table.feed((ROOT / 'tmp/country-coordinates.html').read_text(encoding='utf-8'))
    countries = {}
    for code, lat, lon, name in table.rows:
        if len(code) != 2 or not lat or not lon:
            continue
        x, y = project(float(lon), float(lat))
        countries[code] = {'name': name, 'x': round(x, 2), 'y': round(y, 2)}
    if not all(code in countries for code in ('GB', 'HK', 'SG', 'US', 'CN')):
        raise ValueError('Country reference table was incomplete')
    result = {'source': 'https://developers.google.com/public-data/docs/canonical/countries_csv',
              'note': 'Country reference points, not visitor coordinates. Unmapped codes remain in totals and lists.',
              'countries': countries}
    (ROOT / 'assets/data/visitor-countries.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Prepared {len(paths)} land rings and {len(countries)} country reference points.')


if __name__ == '__main__':
    main()
