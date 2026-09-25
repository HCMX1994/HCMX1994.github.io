/* Lossless, reciprocal single-frequency PORT model; scalar radiation illustration.
 * No element pattern, mutual coupling, structural scattering, or hardware loss.
 * All incident vectors are normalised to equal captured port power.
 */
(function (host) {
  'use strict';
  const N=8, GROUP_SIZE=2, TAU=2*Math.PI, positions=Array.from({length:N},(_,i)=>(i-(N-1)/2)*.5);
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
  // Constrained epigraph search for this eight-element demonstration. Phases and
  // pair mixing angles preserve the architecture's power constraints exactly.
  // Augmented-Lagrangian BFGS is a local method: report convergence separately
  // from feasibility and retain feasible baselines rather than inventing a gain.
  const minimax=(function(){
const K=Array.from({length:N},(_,i)=>Math.PI*(i-3.5));
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0), norm=a=>Math.sqrt(dot(a,a));
function bfgs(fun,start,limit=100,tol=1e-7){
  let x=start.slice(),r=fun(x),n=x.length,H=Array.from({length:n},(_,i)=>Array.from({length:n},(_,j)=>+(i===j))),iterations=0;
  for(;iterations<limit;iterations++){
    if(norm(r.g)<tol)break;
    let d=H.map(row=>-dot(row,r.g)),gd=dot(r.g,d);
    if(gd>=-1e-16){H=Array.from({length:n},(_,i)=>Array.from({length:n},(_,j)=>+(i===j)));d=r.g.map(v=>-v);gd=-dot(r.g,r.g);}
    let step=Math.min(1,2/Math.max(2,norm(d))),next,y;
    for(let ls=0;ls<32;ls++,step*=.5){y=x.map((v,i)=>v+step*d[i]);next=fun(y);if(Number.isFinite(next.f)&&next.f<=r.f+1e-4*step*gd)break;}
    if(!next||next.f>r.f+1e-4*step*gd)break;
    const s=y.map((v,i)=>v-x[i]),dg=next.g.map((v,i)=>v-r.g[i]),sy=dot(s,dg);
    if(sy>1e-14){const Hy=H.map(row=>dot(row,dg)),a=(sy+dot(dg,Hy))/(sy*sy);H=H.map((row,i)=>row.map((v,j)=>v+a*s[i]*s[j]-(Hy[i]*s[j]+s[i]*Hy[j])/sy));}
    x=y;r=next;
  }
  return {x,...r,iterations};
}
function setup(a,target,strength,bd,extra=[]){
  const mag=a.map(z=>Math.hypot(z.re,z.im)),radii=Array.from({length:4},(_,i)=>Math.hypot(mag[2*i],mag[2*i+1])),u0=Math.sin(target*Math.PI/180),guard=.28;
  const floor=mag.reduce((s,v)=>s+v,0)**2/N*10**(-2*strength/10),u=[];
  for(let i=0;i<=160;i++)u.push(-1+i/80);
  for(const v of [u0-guard,u0+guard,...extra])if(v>=-1&&v<=1)u.push(v);
  const rows=u.map(v=>({u:v,side:Math.abs(v-u0)>=guard-1e-12,c:K.map(k=>Math.cos(k*(v-u0))),s:K.map(k=>Math.sin(k*(v-u0)))}));
  const n=bd?13:9,tIndex=n-1;
  function waves(x){const re=[],im=[],dr=[],di=[];
    for(let i=0;i<N;i++){const amp=bd?radii[i>>1]*(i%2?Math.sin(x[8+(i>>1)]):Math.cos(x[8+(i>>1)])):mag[i];re[i]=amp*Math.cos(x[i]);im[i]=amp*Math.sin(x[i]);if(bd){const d=radii[i>>1]*(i%2?Math.cos(x[8+(i>>1)]):-Math.sin(x[8+(i>>1)]));dr[i]=d*Math.cos(x[i]);di[i]=d*Math.sin(x[i]);}}
    return {re,im,dr,di};
  }
  function evaluate(x,lambda,rho){
    const {re,im,dr,di}=waves(x),sr=re.reduce((s,v)=>s+v,0),si=im.reduce((s,v)=>s+v,0),p0=(sr*sr+si*si)/N;
    const er=-dot(K,im),ei=dot(K,re),h=2*(sr*er+si*ei)/(N*Math.PI*N),gr=Array(N).fill(0),gi=Array(N).fill(0),g=Array(n).fill(0),constraints=[];
    let f=x[tIndex],ti=1,index=0,side=0,main=0;
    function addConstraint(v,pr,pi,dt){constraints.push(v);const w=Math.max(0,lambda[index]+rho*v);f+=(w*w-lambda[index]*lambda[index])/(2*rho);index++;for(let j=0;j<N;j++){gr[j]+=w*pr[j];gi[j]+=w*pi[j];}ti+=w*dt;}
    addConstraint(floor+2e-6-p0,Array(N).fill(-2*sr/N),Array(N).fill(-2*si/N),0);
    for(const row of rows){let xr=0,xi=0;for(let j=0;j<N;j++){xr+=re[j]*row.c[j]-im[j]*row.s[j];xi+=re[j]*row.s[j]+im[j]*row.c[j];}
      const p=(xr*xr+xi*xi)/N,pr=[],pi=[];for(let j=0;j<N;j++){pr[j]=2*(xr*row.c[j]+xi*row.s[j])/N;pi[j]=2*(-xr*row.s[j]+xi*row.c[j])/N;if(!row.side){pr[j]-=2*sr/N;pi[j]-=2*si/N;}}
      if(row.side){side=Math.max(side,p);addConstraint(p-x[tIndex],pr,pi,-1);}else{main=Math.max(main,p-p0);addConstraint(p-p0,pr,pi,0);}
    }
    const wh=lambda[index]+rho*h;f+=lambda[index]*h+rho*h*h/2;
    for(let j=0;j<N;j++){gr[j]+=wh*2*(er+K[j]*si)/(N*Math.PI*N);gi[j]+=wh*2*(ei-K[j]*sr)/(N*Math.PI*N);g[j]=-im[j]*gr[j]+re[j]*gi[j];if(bd)g[8+(j>>1)]+=dr[j]*gr[j]+di[j]*gi[j];}g[tIndex]=ti;
    return {f,g,constraints,h,p0,side,main,waves:{re,im}};
  }
  const initial=(phases=Array(N).fill(0))=>[...phases,...(bd?radii.map((r,i)=>Math.atan2(mag[2*i+1],mag[2*i])):[]),.08];
  return {evaluate,initial,waves,rows,floor,tIndex,n,target,bd,mag};
}
function solve(ctx,start,outerLimit=12){let x=start.slice(),lambda=Array(ctx.rows.length+2).fill(0),rho=20,prev=Infinity,total=0,r;
  for(let outer=0;outer<outerLimit;outer++){
    r=bfgs(v=>ctx.evaluate(v,lambda,rho),x,130,1e-7);x=r.x;total+=r.iterations;
    const violation=Math.max(Math.abs(r.h),...r.constraints,0);
    for(let i=0;i<r.constraints.length;i++)lambda[i]=Math.max(0,lambda[i]+rho*r.constraints[i]);lambda[lambda.length-1]+=rho*r.h;
    if(violation<1e-8&&norm(r.g)<2e-6)break;
    if(violation>prev*.3)rho=Math.min(1e7,rho*5);prev=violation;
  }
  return {...r,x,total,violation:Math.max(Math.abs(r.h),...r.constraints,0),grad:norm(r.g)};
}
// Find actual local maxima between angular samples as well as both guard edges.
// This is a numerical angular check, not a certificate of global optimisation.
function inspect(waves,target,guard=.28){
  const u0=Math.sin(target*Math.PI/180),{re,im}=waves;
  function p(u){let r=0,i=0;for(let j=0;j<N;j++){const co=Math.cos(K[j]*(u-u0)),si=Math.sin(K[j]*(u-u0));r+=re[j]*co-im[j]*si;i+=re[j]*si+im[j]*co;}return (r*r+i*i)/N;}
  function interval(lo,hi){if(lo>hi)return [];const steps=Math.max(2,Math.ceil((hi-lo)*512)),du=(hi-lo)/steps,values=Array.from({length:steps+1},(_,i)=>p(lo+i*du)),peaks=[{u:lo,p:values[0]},{u:hi,p:values[steps]}];
    for(let j=1;j<steps;j++)if(values[j]>=values[j-1]&&values[j]>=values[j+1]){
      let left=lo+(j-1)*du,right=lo+(j+1)*du;
      for(let k=0;k<45;k++){const a=left+(right-left)/3,b=right-(right-left)/3;if(p(a)>p(b))right=b;else left=a;}
      const u=(left+right)/2;peaks.push({u,p:p(u)});
    }return peaks;
  }
  const sidePeaks=[...interval(-1,Math.min(1,u0-guard)),...interval(Math.max(-1,u0+guard),1)],mainPeaks=interval(Math.max(-1,u0-guard),Math.min(1,u0+guard));
  const max=rows=>rows.reduce((a,b)=>b.p>a.p?b:a,rows[0]),side=max(sidePeaks),peak=max([...mainPeaks,...sidePeaks,{u:u0,p:p(u0)}]);
  return {side:side.p,sidePeaks,peak:{angle:Math.asin(peak.u)*180/Math.PI,power:peak.p},target:p(u0)};
}
function optimise(a,target,strength,starts=16){
  const result={};
  for(const bd of [false,true]){
    let ctx=setup(a,target,strength,bd),seed=331,feasibleStarts=0,bestStart=0;const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
    const evaluate=x=>{const r=ctx.evaluate(x,Array(ctx.rows.length+2).fill(0),20);return {...r,x,violation:Math.max(Math.abs(r.h),...r.constraints,0),grad:Infinity,total:0};};
    let baseline=ctx.initial(bd?result.d.x.slice(0,8):undefined);
    baseline[ctx.tIndex]=inspect(ctx.waves(baseline),target).side;
    let best=evaluate(baseline),bestScan=inspect(best.waves,target),records=[];
    const acceptable=(r,scan)=>r.p0>=ctx.floor-1e-9&&Math.abs(r.h)<2e-7&&scan.peak.power<=r.p0+1e-7&&Math.abs(scan.peak.angle-target)<.02;
    for(let s=0;s<starts;s++){
      let x=ctx.initial(s===0?baseline.slice(0,8):Array.from({length:N},()=> (rand()-.5)*(s%3===0?3:1.4)));
      if(bd&&s>1)for(let g=0;g<4;g++)x[8+g]+=(rand()-.5)*.7;
      x[ctx.tIndex]=inspect(ctx.waves(x),target).side;
      const r=solve(ctx,x),scan=inspect(r.waves,target);
      if(acceptable(r,scan)){feasibleStarts++;records.push({r,scan});if(scan.side<bestScan.side){best=r;bestScan=scan;bestStart=s;}}
    }
    // Exchange off-grid maxima into the constraints and polish several good starts.
    records.sort((a,b)=>a.scan.side-b.scan.side);
    for(const record of records.slice(0,3)){
      let r=record.r,scan=record.scan,extra=[];
      for(let pass=0;pass<4;pass++){
        extra.push(...scan.sidePeaks.map(p=>p.u));ctx=setup(a,target,strength,bd,extra);
        r=solve(ctx,r.x);scan=inspect(r.waves,target);
        if(acceptable(r,scan)&&scan.side<bestScan.side){best=r;bestScan=scan;}
        if(scan.side-r.x[ctx.tIndex]<2e-8&&r.violation<1e-7&&r.grad<2e-5)break;
      }
    }
    // A finite-grid candidate can beat its own polished result by a tiny amount.
    // Polish the selected candidate too; retain its feasible predecessor if needed.
    ctx=setup(a,target,strength,bd,bestScan.sidePeaks.map(p=>p.u));
    const refined=solve(ctx,best.x),refinedScan=inspect(refined.waves,target);
    if(acceptable(refined,refinedScan)&&refinedScan.side<=bestScan.side+1e-9){best=refined;bestScan=refinedScan;}
    result[bd?'b':'d']={...best,scan:bestScan,starts,feasibleStarts,bestStart,converged:best.violation<1e-7&&best.grad<2e-5&&bestScan.side-best.x[ctx.tIndex]<1e-6,floor:ctx.floor};
  }
  return result;
}
return {setup,solve,inspect,optimise};
  })();

  function groupPeak(a,target) {
    return steering(target).map((z,i)=>scale(z,Math.sqrt((abs2(a[i-i%2])+abs2(a[i-i%2+1]))/2)));
  }
  function metrics(b,obj) {
    const v=steering(obj.target),z=b.map((b,i)=>mul(b,conj(v[i]))),waves={re:z.map(b=>b.re),im:z.map(b=>b.im)};
    const checked=minimax.inspect(waves,obj.target,obj.guard),target=arrayPower(b,obj.target);
    return {target,peak:checked.peak,side:checked.side,sideToTarget:checked.side/Math.max(target,1e-12),score:obj.goal==='peak'?target:-checked.side,plot:pattern(b)};
  }
  const solutionCache=new Map();
  function compare({field='near',incidence=45,range=5,target=0,goal='sidelobes',strength=.5,searchStarts=16}={}) {
    const a=illumination(field,incidence,range),v=steering(target),aligned=v.map((z,i)=>scale(z,Math.sqrt(abs2(a[i]))));
    const reference=arrayPower(aligned,target),obj={goal,target,guard:2.24/N,lossDb:2*strength,powerFloor:reference*10**(-2*strength/10),reference};
    let desiredD=aligned,desiredB=groupPeak(a,target),search=null;
    if(goal==='sidelobes'){
      // Incident phases can be compensated by either lossless network. Reuse only
      // optimisation of output waves with the SAME magnitudes and target settings.
      const key=JSON.stringify([a.map(z=>Math.sqrt(abs2(z)).toFixed(12)),target,strength,searchStarts]);
      search=solutionCache.get(key);
      if(!search){search=minimax.optimise(a,target,strength,searchStarts);if(solutionCache.size>=24)solutionCache.delete(solutionCache.keys().next().value);solutionCache.set(key,search);}
      const output=r=>r.waves.re.map((re,i)=>mul(c(re,r.waves.im[i]),v[i]));
      desiredD=output(search.d);desiredB=output(search.b);
    }
    const S_d=diagonalNetwork(a,desiredD),joint=groupNetwork(a,desiredB),d=apply(S_d,a),b=joint.b,dMetrics=metrics(d,obj),bMetrics=metrics(b,obj);
    if(goal==='sidelobes'){
      for(const m of [dMetrics,bMetrics])if(m.target<obj.powerFloor-1e-8||Math.abs(m.peak.angle-target)>.02||m.peak.power>m.target+1e-7)throw new Error('Minimax main-beam constraints were not met');
      if(bMetrics.side>dMetrics.side+1e-8)throw new Error('BD result is worse than the feasible D-RIS candidate');
    }
    const diagnostics=r=>r?{starts:r.starts,feasibleStarts:r.feasibleStarts,converged:r.converged,constraintResidual:r.violation,gradientResidual:r.grad,angularGap:Math.max(0,r.scan.side-r.x.at(-1))}:null;
    return {a,obj,phase:{b:d,S:S_d,aligned,score:dMetrics.score},joint,S_d,S_b:joint.S,input:a,d,b,dMetrics,bMetrics,search:search?{d:diagnostics(search.d),b:diagnostics(search.b)}:null,operation:'reflection',field};
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
  const api={N,GROUP_SIZE,positions,c,add,sub,mul,scale,conj,abs2,power,normalise,apply,dot,steering,illumination,arrayPower,pattern,scattering,pairMap,groupNetwork,groupPeak,minimax,metrics,compare,paired,diagnostics};
  if(typeof module!=='undefined'&&module.exports) module.exports=api;else host.BDRISModel=api;
  // The same versioned model also runs in a worker, leaving page controls responsive.
  if(typeof importScripts==='function'&&typeof document==='undefined')host.onmessage=event=>{
    const {id,state}=event.data;
    try{host.postMessage({id,result:compare(state)});}catch(error){host.postMessage({id,error:error.message});}
  };
})(typeof window!=='undefined'?window:this);
