/* Offline presentation of saved Umami aggregates; no tracking or API requests. */
(() => {
  'use strict';
  const source = document.getElementById('visitor-map-data');
  const panel = document.getElementById('visitors');
  if (!source || !panel) return;
  const data = JSON.parse(source.textContent);
  const select = document.getElementById('visitor-country');
  const detail = document.getElementById('visitor-location-detail');
  const format = new Intl.NumberFormat('en');
  const percent = count => data.visits ? `${(count / data.visits * 100).toFixed(1)}%` : '0.0%';
  const regionNames = new Intl.DisplayNames(['en'], {type: 'region'});
  const regionName = row => row.code ? regionNames.of(row.code) || row.name : row.name;
  const key = row => row.code || 'unknown';
  function render() {
    const country = data.countries.find(row => key(row) === select.value);
    const rows = country ? country.cities : data.countries;
    const title = document.createElement('p');
    title.className = 'visitor-detail-title';
    title.textContent = country
      ? `${regionName(country)} · ${format.format(country.visits)} visits · ${percent(country.visits)} of all archived visits`
      : `Leading locations · share of all ${format.format(data.visits)} archived visits`;
    const table = document.createElement('table');
    table.className = 'visitor-location-table';
    const head = table.createTHead().insertRow();
    for (const label of [country ? 'City' : 'Location', 'Visits', 'Share']) {
      const cell = document.createElement('th'); cell.scope = 'col'; cell.textContent = label; head.append(cell);
    }
    const body = table.createTBody();
    for (const row of rows.slice(0, country ? 5 : 3)) {
      const tr = body.insertRow();
      for (const value of [country ? row.name : regionName(row), format.format(row.visits), percent(row.visits)]) {
        tr.insertCell().textContent = value;
      }
    }
    detail.replaceChildren(title, table);
    if (!rows.length) {
      const empty = document.createElement('p'); empty.textContent = 'No archived locations yet.'; detail.append(empty);
    }
    if (country && rows.length > 5) {
      const more = document.createElement('a'); more.href = '/files/visitor-history.html';
      more.textContent = `View all ${rows.length} cities in the archive →`; detail.append(more);
    }
    for (const marker of panel.querySelectorAll('[data-country]')) {
      marker.setAttribute('aria-pressed', String(marker.dataset.country === select.value));
    }
  }
  select.addEventListener('change', render);
  for (const marker of panel.querySelectorAll('[data-country]')) {
    const activate = () => {select.value = marker.dataset.country; render();};
    marker.addEventListener('click', activate);
    marker.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); activate();}
    });
  }
  // A cached page must not label last month's count as this month's visitors.
  const parts = new Intl.DateTimeFormat('en', {timeZone: data.timezone, year: 'numeric', month: '2-digit'}).formatToParts(new Date());
  const thisMonth = `${parts.find(p => p.type === 'year').value}-${parts.find(p => p.type === 'month').value}`;
  if (thisMonth !== data.current_month) {
    document.getElementById('visitor-current-count').textContent = '—';
    document.getElementById('visitor-current-month').textContent = thisMonth;
    document.getElementById('visitor-current-note').textContent = 'Awaiting this month’s export';
  }
  render();
})();
