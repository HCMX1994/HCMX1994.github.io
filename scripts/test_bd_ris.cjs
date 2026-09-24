/* Independent invariants for the current eight-element near/far comparison. */
const assert=require('node:assert/strict'), M=require('../assets/js/bd-ris-model.js');
const near=(a,b,tol=1e-9,message='Values differ')=>assert.ok(Math.abs(a-b)<tol,`${message}: ${a} / ${b}`);
const complexNear=(a,b,tol=1e-9)=>near(Math.sqrt(M.abs2(M.sub(a,b))),0,tol,'Complex values differ');
const valid=(S,a)=>{const d=M.diagnostics(S,a);for(const [key,value]of Object.entries(d))near(value,0,1e-9,key);};
// A sphere approaches a plane, up to a common phase, and changes both amplitude and phase nearby.
for(const angle of [-55,0,45,55]) {
  const a=M.illumination('near',angle,1e6),far=M.illumination('far',angle),close=M.illumination('near',angle,5);
  near(M.power(a),1);near(M.power(far),1);near(M.abs2(M.dot(a,far)),1,1e-8,'Spherical-to-plane-wave limit');
  assert.ok(Math.max(...close.map(M.abs2))-Math.min(...close.map(M.abs2))>1e-4,'Actual near-field amplitude variation');
  const n=M.positions.length, centreDistance=5,xs=5*Math.sin(angle*Math.PI/180),zs=5*Math.cos(angle*Math.PI/180);
  const radii=M.positions.map(x=>Math.hypot(x-xs,zs));
  near(M.abs2(close[0])/M.abs2(close[n-1]),(radii[n-1]/radii[0])**2,1e-9,'Inverse-square port power ratio');
}
// Analytic uniform-array sum, null, fixed normalisation, and global-phase invariance.
const uniform=M.illumination('far',0);
near(M.arrayPower(uniform,0),1);near(M.arrayPower(uniform,Math.asin(2/M.N)*180/Math.PI),0);
for(const angle of [-63,-27,0,15,51]) {
  const psi=Math.PI*Math.sin(angle*Math.PI/180),expected=Math.abs(psi)<1e-10?1:(Math.sin(M.N*psi/2)/(M.N*Math.sin(psi/2)))**2;
  near(M.arrayPower(uniform,angle),expected,1e-10,'Analytic uniform-array factor');
  near(M.arrayPower(uniform.map(z=>M.scale(z,.5)),angle),expected/4,1e-10,'Power cannot be individually normalised');
}
let cases=0,maxFit=0;
for(const field of ['near','far'])for(const operation of ['reflection','transmission'])for(const goal of ['peak','sidelobes'])for(const target of [-55,-31,0,33,55])for(const strength of [.05,.5,1]) {
  const r=M.compare({field,operation,goal,target,strength});
  valid(r.S_d,r.input);valid(r.S_b,r.input);near(M.power(r.d),1);near(M.power(r.b),1);
  r.d.forEach((z,i)=>near(M.abs2(z),M.abs2(r.a[i]),1e-10,'Phase-only magnitudes'));
  assert.ok(r.bMetrics.score>=r.dMetrics.score-1e-9,'Enlarged feasible set cannot lower the common objective');
  assert.ok(r.phase.score>=M.score(r.obj.Q,r.phase.aligned)-1e-10,'D-RIS optimisation retains target-aligned candidate');
  near(r.dMetrics.score,r.dMetrics.target-r.obj.weight*r.dMetrics.meanSide,1e-9,'Objective independently reconstructed from angular powers');
  near(r.bMetrics.score,r.bMetrics.target-r.obj.weight*r.bMetrics.meanSide,1e-9);
  if(goal==='peak') {
    near(r.dMetrics.target,r.a.reduce((s,z)=>s+Math.sqrt(M.abs2(z)),0)**2/M.N,1e-9,'Analytic phase-only bound');
    near(r.bMetrics.target,1,1e-9,'Coherent bound');near(r.dMetrics.peak.angle,target);near(r.bMetrics.peak.angle,target);
    if(field==='far')near(r.dMetrics.target,r.bMetrics.target,1e-9,'Uniform plane wave peak tie');
    else assert.ok(r.bMetrics.target>r.dMetrics.target+1e-4,'Spherical amplitude redistribution improves peak');
  }
  if(operation==='transmission')for(const S of [r.S_d,r.S_b])for(let i=0;i<M.N;i++)for(let j=0;j<M.N;j++) {
    near(M.abs2(S[i][j]),0);near(M.abs2(S[i+M.N][j+M.N]),0);
    complexNear(S[i][j+M.N],S[j+M.N][i]);
  }
  const arbitrary=r.input.map((_,i)=>M.c(Math.cos(.9*i),Math.sin(.7*i)));valid(r.S_b,arbitrary);
  maxFit=Math.max(maxFit,r.joint.residual);cases++;
}
// The D-RIS solver actually changes phase when beneficial, instead of copying peak steering.
const phaseCase=M.compare({field:'near',target:53,strength:1});
assert.ok(phaseCase.phase.score-M.score(phaseCase.obj.Q,phaseCase.phase.aligned)>1e-6,'Nontrivial phase-only optimisation');
// Spectrum and eigenvector are checked against direct quadratic evaluation.
for(const target of [-55,0,37,55]) {
  const obj=M.objective(target,10),e=M.largestEigenvector(obj.Q);near(e.residual,0,1e-8);
  for(let i=0;i<20;i++) {
    const trial=M.normalise(Array.from({length:M.N},(_,j)=>M.c(Math.sin(i*7+j*3),Math.cos(j*5+i*2))));
    assert.ok(M.score(obj.Q,trial)<=e.value/M.N+1e-9,'Dominant Rayleigh quotient');
  }
}
// Transmission lift must work for non-symmetric unitary T as well: reverse block is T^T.
const permutation=Array.from({length:M.N},(_,i)=>Array.from({length:M.N},(_,j)=>M.c(j===(i+1)%M.N?1:0)));
valid(M.liftTransmission(permutation),Array.from({length:2*M.N},(_,i)=>M.c(Math.cos(i),Math.sin(i*.3))));
let pairs=0;
for(const field of ['near','far'])for(const share of [0,.05,.5,.95,1])for(const reflected of [-55,0,55])for(const transmitted of [-55,0,55]) {
  const r=M.paired({field,share,reflected,transmitted});valid(r.S,r.a);near(r.rPower,1-share);near(r.tPower,share);
  for(let m=0;m<M.N;m++)near(M.abs2(r.b[2*m])+M.abs2(r.b[2*m+1]),M.abs2(r.a[2*m]),1e-10,'Pair conserves its own power');
  if(share<1)near(r.rPattern.reduce((a,b)=>a.power>b.power?a:b).angle,reflected);
  if(share>0)near(r.tPattern.reduce((a,b)=>a.power>b.power?a:b).angle,transmitted);
  valid(r.S,Array.from({length:2*M.N},(_,i)=>M.c(Math.sin(i*.9),Math.cos(i*.7))));pairs++;
}
const p=M.paired({field:'near',reflected:10}),q=M.paired({field:'near',reflected:40});p.t.forEach((z,i)=>complexNear(z,q.t[i]));
console.log(`PASS: ${cases} near/far × reflection/transmission × objective comparisons; worst S-to-wave fit ${maxFit.toExponential(3)}.`);
console.log(`PASS: ${pairs} paired-array states, including reverse/coherent excitation, group conservation and independent steering.`);
console.log('PASS: spherical/plane-wave limit, analytic array factor and bounds, phase-only optimisation, eigensolver, common objective and reciprocal transmission lift.');
