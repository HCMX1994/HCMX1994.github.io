/* Sweep current visible controls; not a full-wave or hardware validation. */
const assert=require('node:assert/strict'),M=require('../assets/js/bd-ris-model.js');
let count=0,maxFit=0,maxInvariant=0,maxPeakOffset=0;
function check(options) {
  const r=M.compare(options);count++;maxFit=Math.max(maxFit,r.joint.residual);
  for(const S of [r.S_d,r.S_b]) {
    const d=M.diagnostics(S,r.input);maxInvariant=Math.max(maxInvariant,...Object.values(d));
    assert.ok(Math.max(...Object.values(d))<1e-8,`Invalid network ${JSON.stringify(options)}`);
  }
  assert.ok(r.bMetrics.score>=r.dMetrics.score-1e-8,'Common-objective feasible-set bound');
  assert.ok(r.phase.score>=M.score(r.obj.Q,r.phase.aligned)-1e-9,'Phase-only candidate retained');
  for(const metrics of [r.dMetrics,r.bMetrics]) {
    assert.ok(Number.isFinite(metrics.score)&&Number.isFinite(metrics.sideToTarget));
    assert.ok(metrics.peak.power<=1+1e-9,'Common power bound');
    maxPeakOffset=Math.max(maxPeakOffset,Math.abs(metrics.peak.angle-(options.target||0)));
    if(options.goal==='peak')assert.ok(Math.abs(metrics.peak.angle-options.target)<.26,'Peak steering follows target');
  }
}
// Every one-degree target setting in all field / face / objective combinations.
for(const field of ['near','far'])for(const operation of ['reflection','transmission'])for(const goal of ['peak','sidelobes'])for(let target=-55;target<=55;target++)check({field,operation,goal,target});
// Every near-distance step and source-angle boundaries, for both faces.
for(const operation of ['reflection','transmission'])for(const incidence of [-55,0,55])for(let range=5;range<=20;range+=.5)check({field:'near',operation,incidence,range,target:23});
// Every suppression preference at centre/edge beams under near/far incidence.
for(const field of ['near','far'])for(const target of [-55,0,55])for(let step=1;step<=20;step++)check({field,target,strength:step/20});
let pairs=0;
for(const field of ['near','far'])for(let angle=-55;angle<=55;angle++)for(const share of [0,.5,1]) {
  const r=M.paired({field,reflected:angle,transmitted:-angle,share}),d=M.diagnostics(r.S,r.a);
  assert.ok(Math.max(...Object.values(d))<1e-9);assert.ok(Math.abs(r.rPower+r.tPower-1)<1e-9);pairs++;
}
console.log(`PASS: ${count} comparison states and ${pairs} paired states. Max wave-fit residual ${maxFit.toExponential(3)}; network invariant error ${maxInvariant.toExponential(3)}.`);
console.log(`Suppression objective can shift the actual peak: largest offset in this grid ${maxPeakOffset} degrees; target marker is a requested direction, not a forced rotation.`);
