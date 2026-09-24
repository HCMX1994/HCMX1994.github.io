/* Public snapshots only. No API keys or visitor identifiers are stored here. */
(() => {
  'use strict';
  const ownScript = document.currentScript;
  const base = new URL('../data/', ownScript.src);
  // Preserve the provider's SVG coordinate system when its host becomes narrower.
  const visitorMap = document.querySelector('.visitor-map');
  if (visitorMap) {
    const fitVisitorMap = () => {
      const svg = visitorMap.querySelector('.jvectormap-container svg');
      if (!svg) return false;
      const width = Number(svg.getAttribute('width'));
      const height = Number(svg.getAttribute('height'));
      if (!(width > 0 && height > 0)) return false;
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      visitorMap.style.setProperty('--visitor-map-ratio', `${width} / ${height}`);
      return true;
    };
    if (!fitVisitorMap()) {
      const observer = new MutationObserver(() => { if (fitVisitorMap()) observer.disconnect(); });
      observer.observe(visitorMap, {childList: true, subtree: true});
    }
  }
  async function json(name) {
    const response = await fetch(new URL(name, base), {cache: 'no-cache'});
    if (!response.ok) throw new Error('Data unavailable');
    return response.json();
  }
  if (document.querySelector('[data-scholar="citations"]')) {
    json('scholar.json').then(data => {
      const keys = ['citations', 'h_index', 'i10_index'];
      if (data.author_id !== 'vj_3bhQAAAAJ' || !keys.every(k => Number.isSafeInteger(data[k]) && data[k] >= 0)) throw new Error('Invalid metrics');
      if (!/^\d{4}-\d{2}-\d{2}$/.test(data.updated_at)) throw new Error('Invalid date');
      keys.forEach(k => {document.querySelector(`[data-scholar="${k}"]`).textContent = data[k].toLocaleString('en-GB');});
      const date = new Date(`${data.updated_at}T00:00:00Z`);
      const stale = Date.now() - date.getTime() > 7 * 86400000;
      document.getElementById('scholar-status').textContent = `Google Scholar · Last verified ${date.toLocaleDateString('en-GB', {day:'numeric',month:'short',year:'numeric',timeZone:'UTC'})}${stale ? ' · Update pending' : ''}`;
    }).catch(() => {document.getElementById('scholar-status').textContent = 'Metrics temporarily unavailable. View the latest figures on Google Scholar.';});
  }
})();
