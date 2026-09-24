# Offline visitor map reference data

The map uses **Umami aggregates only**. Geographic assets below are static reference data, not analytics services; no visitor data is sent to either source.

- Land outline: Natural Earth 1:110m via [world-atlas 2.0.2](https://github.com/topojson/world-atlas), [land-110m.json](https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/land-110m.json). Converted to equirectangular SVG, with antimeridian rings unwrapped and Antarctica omitted. Natural Earth data is public domain.
- Country/region reference points: [Google DSPL countries.csv](https://developers.google.com/public-data/docs/canonical/countries_csv), retrieved 24 September 2026. Coordinates were projected into the SVG view box. The source is attributed in the map footer; its page content is licensed under CC BY 4.0. Labels do not imply exact visitor locations. Missing reference codes remain visible in the count/list, without invented coordinates.
- `scripts/prepare_visitor_map.py` is the one-time conversion utility. It reads downloaded inputs from `tmp/` and produces `images/visitor-world.svg` and `assets/data/visitor-countries.json`. Normal builds only read committed assets; no remote geography service or additional Python package is needed.

## world-atlas ISC notice

Copyright 2013-2019 Michael Bostock

Permission to use, copy, modify, and/or distribute this software for any purpose
with or without fee is hereby granted, provided that the above copyright notice
and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF
THIS SOFTWARE.
