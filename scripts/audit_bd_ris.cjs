/* Sweep current visible controls; not a full-wave or hardware validation. */
const assert=require('node:assert/strict'),M=require('../assets/js/bd-ris-model.js');
let count=0,maxFit=0,maxInvariant=0,maxPeakOffset=0;
function check(options) {
  const r=M.compare(options);count++;maxFit=Math.max(maxFit,r.joint.residual);
  for(const S of [r.S_d,r.S_b]) {
    const d=M.diagnostics(S,r.input);maxInvariant=Math.max(maxInvariant,...Object.values(d));
    assert.ok(Math.max(...Object.values(d))<1e-8,`Invalid network ${JSON.stringify(options)}`);
  }
  for(let g=0;g<M.N;g+=2)assert.ok(Math.abs(M.power(r.b.slice(g,g+2))-M.power(r.a.slice(g,g+2)))<1e-9,'Each reflection group conserves its own power');
  for(let i=0;i<M.N;i++)for(let j=0;j<M.N;j++)if(Math.floor(i/2)!==Math.floor(j/2))assert.equal(M.abs2(r.S_b[i][j]),0,'No inter-group links');
  assert.ok(r.bMetrics.score>=r.dMetrics.score-1e-8,'Common-objective feasible-set bound');
  const aligned=M.metrics(r.phase.aligned,r.obj);
  assert.ok(r.phase.score>=aligned.score-1e-8,'Phase-only candidate retained');
  for(const metrics of [r.dMetrics,r.bMetrics]) {
    assert.ok(Number.isFinite(metrics.score)&&Number.isFinite(metrics.sideToTarget));
    assert.ok(metrics.peak.power<=1+1e-9,'Common power bound');
    maxPeakOffset=Math.max(maxPeakOffset,Math.abs(metrics.peak.angle-(options.target||0)));
    assert.ok(Math.abs(metrics.peak.angle-(options.target||0))<.02,'Main beam remains at the requested direction');
    if(options.goal!=='peak')assert.ok(metrics.target>=r.obj.powerFloor-1e-8,'Same minimum target power');
  }
}
// Full target slider in the analytic mode; representative minimax boundaries,
// asymmetric illuminations and intermediate power floors (each is a multi-start solve).
for(const field of ['near','far'])for(let target=-55;target<=55;target++)check({field,goal:'peak',target});
for(const field of ['near','far'])for(const target of [-55,-41,-17,5,23,49,55])check({field,target,strength:.65});
for(const incidence of [-55,0,55])for(const range of [5,12.5,20])check({field:'near',incidence,range,target:23});
for(const field of ['near','far'])for(const target of [-55,0,55])for(const strength of [.15,.85])check({field,target,strength});
let pairs=0;
for(const field of ['near','far'])for(let angle=-55;angle<=55;angle++)for(const share of [0,.5,1]) {
  const r=M.paired({field,reflected:angle,transmitted:-angle,share}),d=M.diagnostics(r.S,r.a);
  assert.ok(Math.max(...Object.values(d))<1e-9);assert.ok(Math.abs(r.rPower+r.tPower-1)<1e-9);pairs++;
}
console.log(`PASS: ${count} comparison states and ${pairs} paired states. Max wave-fit residual ${maxFit.toExponential(3)}; network invariant error ${maxInvariant.toExponential(3)}.`);
console.log(`Constrained minimax pointing: largest checked offset ${maxPeakOffset} degrees. Common target-power floor and pair power conservation passed.`);
