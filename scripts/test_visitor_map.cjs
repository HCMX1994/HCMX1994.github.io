const assert=require('node:assert/strict');
const {validate,combine,month}=require('../assets/js/visitor-map.js');
const now=Date.parse('2027-05-01T11:00:10Z');
const sample=()=>({schema_version:1,source:'Umami',website_id:'test',domain:'hcmx1994.github.io',captured_at:'2027-05-01T11:00:00Z',started_at:'2026-09-24T18:00:00Z',timezone:'Europe/London',current_month:'2027-05',current_month_visitors:1,totals:{visits:3,pageviews:5},countries:[{code:'GB',visits:2},{code:null,visits:1}],cities:[{country:'GB',name:'London',visits:2},{country:null,name:null,visits:1}]});
const original=sample();
assert.equal(validate(sample(),original,'test',now).totals.visits,3);
for(const change of [s=>s.totals.visits=2,s=>s.cities.pop(),s=>s.ip='192.0.2.1',s=>s.captured_at='2027-04-01T00:00:00Z',s=>s.website_id='wrong',s=>s.cities[0].name='another city']) {
  const s=sample();change(s);assert.throws(()=>validate(s,original,'test',now));
}
const baseline=sample();baseline.current_month='2026-09';
for(let i=0;i<3;i++) {
  const merged=combine(baseline,sample(),{},new Date(now));
  assert.equal(merged.visits,6);assert.equal(merged.current_visitors,1);
  assert.equal(merged.countries.reduce((s,r)=>s+r.visits,0),6);
}
assert.equal(combine(baseline,sample(),{},new Date('2027-06-01T12:00:00Z')).current_visitors,null);
assert.equal(month(new Date('2026-09-30T23:30:00Z')),'2026-10');
console.log('Visitor model: refresh, migration, geography, stale/reset rejection and UK rollover passed.');
