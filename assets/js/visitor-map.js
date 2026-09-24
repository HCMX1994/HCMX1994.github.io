/* Public aggregates only. Each refresh rebuilds from independent sources. */
const UmamiSummary = (() => {
  'use strict';
  const fields = 'schema_version source website_id domain captured_at started_at timezone current_month current_month_visitors totals countries cities'.split(' ');
  const count = n => Number.isSafeInteger(n) && n >= 0;
  const keys = (value, allowed) => value && Object.keys(value).sort().join('|') === [...allowed].sort().join('|');
  const code = s => s === null || (typeof s === 'string' && /^[A-Z]{2}$/.test(s));
  function month(now) {
    const parts = new Intl.DateTimeFormat('en', {timeZone:'Europe/London',year:'numeric',month:'2-digit'}).formatToParts(now);
    return `${parts.find(p => p.type === 'year').value}-${parts.find(p => p.type === 'month').value}`;
  }
  function validate(next, previous, site, now = Date.now()) {
    if (!keys(next, fields) || next.schema_version !== 1 || next.source !== 'Umami' || next.website_id !== site || next.domain !== 'hcmx1994.github.io' || next.timezone !== 'Europe/London') throw Error('Wrong source');
    const stamp = Date.parse(next.captured_at);
    if (!Number.isFinite(stamp) || stamp > now + 60_000 || now - stamp > 300_000 || next.current_month !== month(new Date(stamp))) throw Error('Stale summary');
    if (!keys(next.totals, ['visits','pageviews']) || !count(next.totals.visits) || !count(next.totals.pageviews) || next.totals.visits > next.totals.pageviews || !count(next.current_month_visitors) || next.current_month_visitors > next.totals.visits) throw Error('Invalid totals');
    if (next.totals.visits ? !Number.isFinite(Date.parse(next.started_at)) || Date.parse(next.started_at) > stamp : next.started_at !== null) throw Error('Invalid start');
    const countries = new Map(), cities = new Map(), cityTotals = new Map();
    for (const r of next.countries) {
      if (!keys(r,['code','visits']) || !code(r.code) || !count(r.visits) || countries.has(r.code)) throw Error('Invalid geography');
      countries.set(r.code, r.visits);
    }
    for (const r of next.cities) {
      const key = JSON.stringify([r.country,r.name]);
      if (!keys(r,['country','name','visits']) || !code(r.country) || !count(r.visits) || cities.has(key) || (r.name !== null && (typeof r.name !== 'string' || r.name.length > 160 || /[\u0000-\u001f]/.test(r.name)))) throw Error('Invalid city');
      cities.set(key,r.visits); cityTotals.set(r.country,(cityTotals.get(r.country)||0)+r.visits);
    }
    if ([...countries.values()].reduce((a,b)=>a+b,0) !== next.totals.visits || countries.size !== cityTotals.size || [...countries].some(([c,n])=>cityTotals.get(c)!==n)) throw Error('Incomplete geography');
    if (previous && (stamp < Date.parse(previous.captured_at) || (previous.started_at && next.started_at !== previous.started_at) || next.totals.visits < previous.totals.visits || next.totals.pageviews < previous.totals.pageviews || previous.countries.some(r=>(countries.get(r.code)||0)<r.visits) || previous.cities.some(r=>(cities.get(JSON.stringify([r.country,r.name]))||0)<r.visits))) throw Error('History decreased');
    return next;
  }
  function combine(baseline, live, reference, now = new Date()) {
    const countries = new Map(), cities = new Map();
    for (const s of [baseline, live]) {
      for (const r of s.countries) countries.set(r.code || '',(countries.get(r.code||'')||0)+r.visits);
      for (const r of s.cities) {
        const key = JSON.stringify([r.country||'',r.name||'Unknown city']);
        cities.set(key,(cities.get(key)||0)+r.visits);
      }
    }
    const byCount = (a,b)=>b.visits-a.visits || a.name.localeCompare(b.name);
    const current = month(now);
    return {visits:baseline.totals.visits+live.totals.visits, current_month:current,
      current_visitors:live.current_month===current ? live.current_month_visitors : null,
      current_label:current===baseline.current_month ? 'Visitors since 24 Sep' : 'Visitors',
      captured_at:live.captured_at, timezone:'Europe/London',
      countries:[...countries].map(([c,n])=>{
        const ref=reference[c];
        return {code:c,name:ref?.name||c||'Unknown location',visits:n,
          point:ref && ref.y>=0 && ref.y<=310 ? [ref.x,ref.y] : null,
          cities:[...cities].flatMap(([k,v])=>{const [country,name]=JSON.parse(k);return country===c ? [{name,visits:v}] : [];}).sort(byCount)};
      }).sort(byCount)};
  }
  return {validate, combine, month};
})();
if (typeof module !== 'undefined') module.exports = UmamiSummary;

if (typeof document !== 'undefined') (() => {
  'use strict';
  const source=document.getElementById('visitor-map-data'), panel=document.getElementById('visitors');
  if (!source || !panel) return;
  let data=JSON.parse(source.textContent);
  const service=data.service, reference=data.reference;
  let saved=service?.snapshot, pending=false;
  const select=document.getElementById('visitor-country'), detail=document.getElementById('visitor-location-detail');
  const format=new Intl.NumberFormat('en'), svg=panel.querySelector('.visitor-world');
  const key=r=>r.code||'unknown';
  const share=n=>data.visits ? `${(n/data.visits*100).toFixed(1)}%` : '0.0%';
  function set(id,value) {const el=document.getElementById(id);if(el)el.textContent=value;}
  function renderDetail() {
    const country=data.countries.find(r=>key(r)===select.value), rows=country ? country.cities : data.countries.slice(0,3);
    const title=document.createElement('p'); title.className='visitor-detail-title';
    title.textContent=country ? `${country.name} · ${format.format(country.visits)} visits · ${share(country.visits)} of all visits` : `Leading locations · share of all ${format.format(data.visits)} visits`;
    const table=document.createElement('table');table.className='visitor-location-table';
    const head=table.createTHead().insertRow();
    for(const text of [country?'City':'Location','Visits','Share']) {const th=document.createElement('th');th.scope='col';th.textContent=text;head.append(th);}
    const body=table.createTBody();
    for(const r of rows) {const tr=body.insertRow();for(const v of [r.name,format.format(r.visits),share(r.visits)]) tr.insertCell().textContent=v;}
    detail.replaceChildren(title,table);
    if(!rows.length) {const empty=document.createElement('p');empty.textContent='No recorded locations yet.';detail.append(empty);}
    for(const marker of panel.querySelectorAll('[data-country]')) marker.setAttribute('aria-pressed',String(marker.dataset.country===select.value));
  }
  function repaint(live=false) {
    const selected=select.value;
    select.replaceChildren(new Option('All locations','all'));
    for(const r of data.countries) select.add(new Option(`${r.name} · ${format.format(r.visits)}`,key(r)));
    select.value=[...select.options].some(o=>o.value===selected)?selected:'all';
    svg.querySelectorAll('.visitor-marker').forEach(el=>el.remove());
    const ns='http://www.w3.org/2000/svg';
    for(const r of data.countries) {
      if(!r.point || !r.visits)continue;
      const g=document.createElementNS(ns,'g'), label=`${r.name}: ${format.format(r.visits)} visits, ${share(r.visits)} of all visits`;
      for(const [name,value] of Object.entries({class:'visitor-marker',role:'button',tabindex:'0','aria-label':label,'aria-pressed':'false','data-country':r.code,transform:`translate(${r.point[0]} ${r.point[1]})`}))g.setAttribute(name,value);
      const title=document.createElementNS(ns,'title');title.textContent=label;g.append(title);
      const radius=Math.min(14,4+2*Math.sqrt(r.visits));
      for(const [cls,rad] of [['visitor-marker-halo',radius+3],['visitor-marker-dot',radius]]) {const c=document.createElementNS(ns,'circle');c.setAttribute('class',cls);c.setAttribute('r',rad);g.append(c);}
      svg.append(g);
    }
    const thisMonth=UmamiSummary.month(new Date());
    set('visitor-total-count',format.format(data.visits));
    set('visitor-country-count',data.countries.filter(r=>r.code&&r.visits).length);
    set('visitor-current-count',thisMonth===data.current_month && data.current_visitors!==null ? format.format(data.current_visitors) : '—');
    set('visitor-current-month',new Date(`${thisMonth}-15T12:00:00Z`).toLocaleDateString('en',{month:'short',year:'numeric',timeZone:'Europe/London'}));
    set('visitor-current-label',data.current_label||'Visitors');
    set('visitor-current-note',thisMonth===data.current_month?'Count for the indicated period':'Awaiting current statistics');
    const timestamp=new Date(data.captured_at).toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/London'});
    set('visitor-refresh-status',`${live?'Updated':'Saved'} ${timestamp} (UK)${live?' · auto-refresh':''}`);
    set('visitor-coverage-note',`${format.format(data.countries.filter(r=>!r.point).reduce((s,r)=>s+r.visits,0))} visits without a map position remain included in totals. Setup / VPN test visits are included.`);
    renderDetail();
  }
  const activate=event=>{
    const marker=event.target.closest('[data-country]');if(!marker)return;
    if(event.type==='keydown' && event.key!=='Enter' && event.key!==' ')return;
    event.preventDefault();const disclosure=panel.querySelector('details');if(disclosure)disclosure.open=true;
    select.value=marker.dataset.country;renderDetail();
  };
  svg.addEventListener('click',activate);svg.addEventListener('keydown',activate);select.addEventListener('change',renderDetail);
  async function refresh() {
    if(!service || pending || document.hidden)return;
    pending=true;
    try {
      const response=await fetch(service.url,{credentials:'omit',signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw Error('Unavailable');
      const next=UmamiSummary.validate(await response.json(),saved,service.website_id);
      const combined=UmamiSummary.combine(service.baseline,next,reference);
      saved=next;data=combined;repaint(true);
    } catch {repaint(false);} finally {pending=false;}
  }
  repaint();refresh();
  if(service) {setInterval(refresh,60000);document.addEventListener('visibilitychange',refresh);}
})();
