/* Lossless, reciprocal single-frequency PORT model; scalar radiation illustration.
 * No element pattern, mutual coupling, structural scattering, or hardware loss.
 * All incident vectors are normalised to equal captured port power.
 */
(function (host) {
  'use strict';
  const N=36, GROUP_SIZE=2, TAU=2*Math.PI, positions=Array.from({length:N},(_,i)=>(i-(N-1)/2)*.5);
  const c=(re=0,im=0)=>({re,im}), add=(a,b)=>c(a.re+b.re,a.im+b.im), sub=(a,b)=>c(a.re-b.re,a.im-b.im);
  const mul=(a,b)=>c(a.re*b.re-a.im*b.im,a.re*b.im+a.im*b.re), scale=(z,k)=>c(z.re*k,z.im*k), conj=z=>c(z.re,-z.im);
  const abs2=z=>z.re*z.re+z.im*z.im, exp=p=>c(Math.cos(p),Math.sin(p));
  const power=a=>a.reduce((s,z)=>s+abs2(z),0), normalise=a=>a.map(z=>scale(z,1/Math.sqrt(power(a))));
  const matrix=(n,fn)=>Array.from({length:n},(_,i)=>Array.from({length:n},(_,j)=>fn(i,j)));
  const apply=(S,a)=>S.map(row=>row.reduce((s,z,j)=>add(s,mul(z,a[j])),c()));
  const dot=(a,b)=>a.reduce((s,z,i)=>add(s,mul(conj(z),b[i])),c());
  const steering=angle=>positions.map(x=>exp(-TAU*x*Math.sin(angle*Math.PI/180)));
  function illumination(field='near',angle=45,range=5) {
    if(field==='far') return normalise(positions.map(x=>exp(TAU*x*Math.sin(angle*Math.PI/180))));
    // Scalar point-source illumination: spherical phase AND 1/r amplitude.
    const xs=range*Math.sin(angle*Math.PI/180), zs=range*Math.cos(angle*Math.PI/180);
    return normalise(positions.map(x=>{const r=Math.hypot(x-xs,zs);return scale(exp(-TAU*(r-range)),1/r);}));
  }
  function arrayPower(b,angle) {return abs2(dot(steering(angle),b))/N;}
  const pattern=b=>Array.from({length:721},(_,i)=>{const angle=-90+i/4,power=arrayPower(b,angle);return {angle,power,db:10*Math.log10(Math.max(power,1e-12))};});
  function scattering(beta) {
    const n=beta.length, rows=beta.map((row,i)=>[...row.map((v,j)=>c(i===j?1:0,v)),...row.map((v,j)=>c(i===j?1:0,-v))]);
    for(let k=0;k<n;k++) {
      let pivot=k;for(let i=k+1;i<n;i++) if(abs2(rows[i][k])>abs2(rows[pivot][k])) pivot=i;
      [rows[k],rows[pivot]]=[rows[pivot],rows[k]];
      const d=rows[k][k];rows[k]=rows[k].map(z=>scale(mul(z,conj(d)),1/abs2(d)));
      for(let i=0;i<n;i++) if(i!==k) {const f=rows[i][k];rows[i]=rows[i].map((z,j)=>sub(z,mul(f,rows[k][j])));}
    }
    return rows.map(row=>row.slice(n));
  }
  function diagonalNetwork(a,b) {return matrix(a.length,(i,j)=>i===j?(abs2(a[i])>1e-28?scale(mul(b[i],conj(a[i])),1/abs2(a[i])):c(1)):c());}
  function pairMap(input,target) {
    // Phase-normalise the input, then use a real orthogonal basis with the
    // input as its first column. In this basis K=[[z,w],[w,-conj(z)*(w/|w|)^2]]
    // maps [1,0] to [z,w] and is symmetric/unitary. Congruence back preserves
    // both properties AND the exact output phase across independent groups.
    const p=power(input),q=power(target);
    if(Math.abs(p-q)>1e-10*Math.max(p,q,1e-12))throw new Error('Pair power mismatch');
    if(p===0)return matrix(2,(i,j)=>c(i===j?1:0));
    const a=input.map(z=>scale(z,1/Math.sqrt(p))),b=target.map(z=>scale(z,1/Math.sqrt(p)));
    const r=a.map(z=>Math.sqrt(abs2(z))),D=a.map((z,i)=>r[i]>0?scale(conj(z),1/r[i]):c(1));
    const y=b.map((z,i)=>mul(conj(D[i]),z)),z=add(scale(y[0],r[0]),scale(y[1],r[1])),w=sub(scale(y[1],r[0]),scale(y[0],r[1]));
    const wp=abs2(w)>0?scale(w,1/Math.sqrt(abs2(w))):c(1),last=scale(mul(conj(z),mul(wp,wp)),-1);
    const off=add(scale(sub(z,last),r[0]*r[1]),scale(w,r[0]**2-r[1]**2));
    const S0=[[add(sub(scale(z,r[0]**2),scale(w,2*r[0]*r[1])),scale(last,r[1]**2)),off],
      [off,add(add(scale(z,r[1]**2),scale(w,2*r[0]*r[1])),scale(last,r[0]**2))]];
    return S0.map((row,i)=>row.map((v,j)=>mul(mul(D[i],D[j]),v)));
  }
  function groupNetwork(a,target) {
    const S=matrix(N,()=>c());
    for(let g=0;g<N;g+=GROUP_SIZE) {
      const block=pairMap(a.slice(g,g+2),target.slice(g,g+2));
      block.forEach((row,i)=>row.forEach((z,j)=>S[g+i][g+j]=z));
    }
    const b=apply(S,a),residual=Math.sqrt(power(b.map((z,i)=>sub(z,target[i]))));
    if(residual>1e-8)throw new Error('Pair-network synthesis did not meet the wave-fit tolerance');
    return {S,b,residual};
  }
  const objectiveCache=new Map();
  function objective(target,weight) {
    const key=`${target}:${weight}`;if(objectiveCache.has(key))return objectiveCache.get(key);
    const u0=Math.sin(target*Math.PI/180),guard=2.24/N;
    // Same guard for both designs, set BEFORE optimisation. Uniform u=sin(theta) grid.
    const us=Array.from({length:16*N+1},(_,i)=>-1+i/(8*N)).filter(u=>Math.abs(u-u0)>guard),angles=us.map(u=>Math.asin(u)*180/Math.PI);
    // Uniform linear array: Q is Toeplitz; compute each separation once.
    const lags=Array.from({length:N},(_,d)=>sub(exp(-Math.PI*d*u0),scale(us.reduce((s,u)=>add(s,exp(-Math.PI*d*u)),c()),weight/us.length)));
    const Q=matrix(N,(i,j)=>i>=j?lags[i-j]:conj(lags[j-i])),obj={Q,angles,guard,weight,target};
    if(objectiveCache.size>=16)objectiveCache.delete(objectiveCache.keys().next().value);
    objectiveCache.set(key,obj);return obj;
  }
  const score=(Q,b)=>dot(b,apply(Q,b)).re/N;
  function phaseOnly(a,obj) {
    const v=steering(obj.target), magnitudes=a.map(z=>Math.sqrt(abs2(z)));
    const aligned=v.map((z,i)=>scale(z,magnitudes[i]));
    let best={b:aligned,score:score(obj.Q,aligned)};
    let seed=91231;const random=()=>{seed=(Math.imul(1664525,seed)+1013904223)>>>0;return seed/4294967296;};
    for(let start=0;obj.weight>0&&start<25;start++) {
      let b=start===0?aligned.slice():aligned.map(z=>mul(z,exp((random()-.5)*TAU)));
      for(let sweep=0;sweep<100;sweep++) {
        const before=score(obj.Q,b);
        for(let i=0;i<N;i++) {
          const q=obj.Q[i].reduce((s,z,j)=>i===j?s:add(s,mul(z,b[j])),c());
          if(abs2(q)>1e-24) b[i]=scale(q,magnitudes[i]/Math.sqrt(abs2(q)));
        }
        if(score(obj.Q,b)-before<1e-12) break;
      }
      const value=score(obj.Q,b);if(value>best.score) best={b,score:value};
    }
    return {...best,S:diagonalNetwork(a,best.b),aligned};
  }
  function groupPeak(a,target) {
    const v=steering(target);
    return v.map((z,i)=>scale(z,Math.sqrt((abs2(a[i-i%2])+abs2(a[i-i%2+1]))/2)));
  }
  function groupOptimise(a,obj,phase) {
    // Product of 18 complex spheres, NOT one full-array power constraint.
    // Block minorisation/ascent: shift each 2x2 block to PSD, maximise its
    // tangent minorant on that pair's sphere. Each step is non-decreasing.
    const radii=Array.from({length:N/2},(_,g)=>Math.sqrt(abs2(a[2*g])+abs2(a[2*g+1]))),aligned=groupPeak(a,obj.target);
    if(obj.weight===0)return {b:aligned,score:score(obj.Q,aligned)};
    let best={b:phase.b.slice(),score:phase.score};
    const starts=[phase.b.slice(),aligned,...[1,2].map(k=>aligned.map((z,i)=>mul(z,exp(Math.sin((i+1)*(k+3))*Math.PI))))];
    for(const b of starts) {
      for(let sweep=0;sweep<100;sweep++) {
        const before=score(obj.Q,b);
        for(let g=0;g<N;g+=2) {
          const external=[c(),c()];
          for(let j=0;j<N;j++)if(j!==g&&j!==g+1)for(let i=0;i<2;i++)external[i]=add(external[i],mul(obj.Q[g+i][j],b[j]));
          const off=obj.Q[g][g+1],rho=Math.sqrt(abs2(off));
          // Equal real diagonal entries contribute a constant on each sphere.
          for(let step=0;step<6;step++) {
            const y=[add(add(scale(b[g],rho),mul(off,b[g+1])),external[0]),add(add(mul(conj(off),b[g]),scale(b[g+1],rho)),external[1])],norm=Math.sqrt(power(y));
            if(norm>1e-20){b[g]=scale(y[0],radii[g/2]/norm);b[g+1]=scale(y[1],radii[g/2]/norm);}
          }
        }
        if(score(obj.Q,b)-before<1e-12)break;
      }
      const value=score(obj.Q,b);if(value>best.score)best={b,score:value};
    }
    return best;
  }
  function metrics(b,obj) {
    const plot=pattern(b), peak=plot.reduce((p,x)=>x.power>p.power?x:p,plot[0]);
    const outside=plot.filter(x=>Math.abs(Math.sin(x.angle*Math.PI/180)-Math.sin(obj.target*Math.PI/180))>obj.guard);
    const side=Math.max(...outside.map(x=>x.power)), target=arrayPower(b,obj.target);
    return {target,peak,side,sideToTarget:side/Math.max(target,1e-12),meanSide:obj.angles.reduce((s,x)=>s+arrayPower(b,x),0)/obj.angles.length,score:score(obj.Q,b),plot};
  }
  function compare({field='near',incidence=45,range=5,target=0,goal='sidelobes',strength=.5}={}) {
    const a=illumination(field,incidence,range), weight=goal==='peak'?0:20*strength, obj=objective(target,weight);
    const phase=phaseOnly(a,obj),desired=groupOptimise(a,obj,phase);
    const joint=groupNetwork(a,desired.b),d=apply(phase.S,a),b=joint.b;
    if(score(obj.Q,b)<score(obj.Q,d)-1e-7) throw new Error('Joint solution is worse than the feasible phase-only reference');
    return {a,obj,phase,joint,S_d:phase.S,S_b:joint.S,input:a,d,b,dMetrics:metrics(d,obj),bMetrics:metrics(b,obj),operation:'reflection',field};
  }
  function paired({field='near',incidence=45,range=5,reflected=-25,transmitted=30,share=.5}={}) {
    const aFront=illumination(field,incidence,range),S=matrix(2*N,()=>c()),a=Array.from({length:2*N},()=>c());
    const blocks=positions.map((x,m)=>{
      const inPhase=Math.atan2(aFront[m].im,aFront[m].re),pr=-TAU*x*Math.sin(reflected*Math.PI/180)-inPhase,pt=-TAU*x*Math.sin(transmitted*Math.PI/180)-inPhase;
      const r=scale(exp(pr),Math.sqrt(1-share)),t=scale(exp(pt),Math.sqrt(share)),rear=scale(exp(2*pt-pr),-Math.sqrt(1-share));
      const block=[[r,t],[t,rear]];block.forEach((row,i)=>row.forEach((z,j)=>S[2*m+i][2*m+j]=z));a[2*m]=aFront[m];return block;
    });
    const b=apply(S,a),r=b.filter((_,i)=>i%2===0),t=b.filter((_,i)=>i%2===1);
    return {S,a,b,r,t,blocks,rPower:power(r),tPower:power(t),rPattern:pattern(r),tPattern:pattern(t)};
  }
  function diagnostics(S,a) {
    let reciprocal=0,unitary=0;
    for(let i=0;i<S.length;i++) for(let j=0;j<S.length;j++) {
      reciprocal=Math.max(reciprocal,Math.sqrt(abs2(sub(S[i][j],S[j][i]))));
      const gram=S.reduce((s,row)=>add(s,mul(conj(row[i]),row[j])),c());
      unitary=Math.max(unitary,Math.sqrt(abs2(sub(gram,c(i===j?1:0)))));
    }
    return {reciprocal,unitary,power:Math.abs(power(apply(S,a))-power(a))};
  }
  const api={N,GROUP_SIZE,positions,c,add,sub,mul,scale,conj,abs2,power,normalise,apply,dot,steering,illumination,arrayPower,pattern,scattering,pairMap,groupNetwork,groupPeak,groupOptimise,objective,score,phaseOnly,metrics,compare,paired,diagnostics};
  if(typeof module!=='undefined'&&module.exports) module.exports=api;else host.BDRISModel=api;
})(typeof window!=='undefined'?window:this);
