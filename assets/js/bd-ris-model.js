/* Lossless, reciprocal single-frequency PORT model; scalar radiation illustration.
 * No element pattern, mutual coupling, structural scattering, or hardware loss.
 * All incident vectors are normalised to equal captured port power.
 */
(function (host) {
  'use strict';
  const N=8, TAU=2*Math.PI, positions=Array.from({length:N},(_,i)=>(i-(N-1)/2)*.5);
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
    // Scalar radiative-near-field point source: spherical phase AND 1/r amplitude.
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
  function diagonalNetwork(a,b) {return matrix(N,(i,j)=>i===j?scale(mul(b[i],conj(a[i])),1/abs2(a[i])):c());}
  function reciprocalMap(a,target) {
    // Real symmetric minimum-norm solution of beta U=V, U=[Re(a+b),Im(a+b)].
    // U^T V is symmetric iff ||a||=||b||. Global phase avoids Cayley singularities.
    if(Math.max(...a.map((z,i)=>Math.abs(abs2(z)-abs2(target[i]))))<1e-12) {
      const S=diagonalNetwork(a,target);return {S,b:apply(S,a),residual:0,beta:null};
    }
    let best=null;
    for(let step=0;step<32;step++) {
      const b=target.map(z=>mul(z,exp(TAU*(step+.31)/32)));
      const U=a.map((z,i)=>{const u=add(z,b[i]);return [u.re,u.im];});
      const V=a.map((z,i)=>{const d=sub(b[i],z);return [-d.im,d.re];});
      const g00=U.reduce((s,u)=>s+u[0]*u[0],0),g01=U.reduce((s,u)=>s+u[0]*u[1],0),g11=U.reduce((s,u)=>s+u[1]*u[1],0),det=g00*g11-g01*g01;
      if(det<1e-12) continue;
      const P=[U.map(u=>(g11*u[0]-g01*u[1])/det),U.map(u=>(g00*u[1]-g01*u[0])/det)];
      const C=matrix(2,(i,j)=>U.reduce((s,u,m)=>s+u[i]*V[m][j],0));
      const beta=matrix(N,(i,j)=>V[i][0]*P[0][j]+V[i][1]*P[1][j]+V[j][0]*P[0][i]+V[j][1]*P[1][i]-P[0][i]*(C[0][0]*P[0][j]+C[0][1]*P[1][j])-P[1][i]*(C[1][0]*P[0][j]+C[1][1]*P[1][j]));
      // Suppress floating-point asymmetry before the Cayley transform.
      for(let i=0;i<N;i++) for(let j=i+1;j<N;j++) beta[i][j]=beta[j][i]=(beta[i][j]+beta[j][i])/2;
      const S=scattering(beta), actual=apply(S,a),residual=Math.sqrt(power(actual.map((z,i)=>sub(z,b[i]))));
      const score=Math.max(...beta.flat().map(Math.abs))+residual*1e9;
      if(!best||score<best.score) best={S,b:actual,beta,residual,score};
    }
    if(!best||best.residual>1e-7) throw new Error('Network synthesis did not meet the wave-fit tolerance');
    return best;
  }
  function objective(target,weight) {
    const v=steering(target), u0=Math.sin(target*Math.PI/180),guard=.28;
    // Same guard for both designs, set BEFORE optimisation. Uniform u=sin(theta) grid.
    const angles=Array.from({length:201},(_,i)=>-1+i*.01).filter(u=>Math.abs(u-u0)>guard).map(u=>Math.asin(u)*180/Math.PI);
    const samples=angles.map(steering);
    const Q=matrix(N,(i,j)=>sub(mul(v[i],conj(v[j])),scale(samples.reduce((s,h)=>add(s,mul(h[i],conj(h[j]))),c()),weight/samples.length)));
    return {Q,angles,guard,weight,target};
  }
  const score=(Q,b)=>dot(b,apply(Q,b)).re/N;
  function phaseOnly(a,obj) {
    const v=steering(obj.target), magnitudes=a.map(z=>Math.sqrt(abs2(z)));
    const aligned=v.map((z,i)=>scale(z,magnitudes[i]));
    let best={b:aligned,score:score(obj.Q,aligned)};
    let seed=91231;const random=()=>{seed=(Math.imul(1664525,seed)+1013904223)>>>0;return seed/4294967296;};
    for(let start=0;start<25;start++) {
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
  function largestEigenvector(Q) {
    // Real symmetric representation of a Hermitian matrix; Jacobi eigensolver.
    const n=2*N,A=matrix(n,(i,j)=>i<N?(j<N?Q[i][j].re:-Q[i][j-N].im):(j<N?Q[i-N][j].im:Q[i-N][j-N].re)), V=matrix(n,(i,j)=>i===j?1:0);
    for(let iteration=0;iteration<5000;iteration++) {
      let p=0,q=1,max=0;for(let i=0;i<n;i++) for(let j=i+1;j<n;j++) if(Math.abs(A[i][j])>max) {max=Math.abs(A[i][j]);p=i;q=j;}
      if(max<1e-12) break;
      const tau=(A[q][q]-A[p][p])/(2*A[p][q]), t=(tau>=0?1:-1)/(Math.abs(tau)+Math.hypot(1,tau)),co=1/Math.hypot(1,t),si=t*co,apq=A[p][q];
      A[p][p]-=t*apq;A[q][q]+=t*apq;A[p][q]=A[q][p]=0;
      for(let i=0;i<n;i++) {
        if(i!==p&&i!==q) {const x=A[i][p],y=A[i][q];A[i][p]=A[p][i]=co*x-si*y;A[i][q]=A[q][i]=si*x+co*y;}
        const x=V[i][p],y=V[i][q];V[i][p]=co*x-si*y;V[i][q]=si*x+co*y;
      }
    }
    let k=0;for(let i=1;i<n;i++) if(A[i][i]>A[k][k]) k=i;
    const b=normalise(Array.from({length:N},(_,i)=>c(V[i][k],V[i+N][k]))), value=dot(b,apply(Q,b)).re;
    const residual=Math.sqrt(power(apply(Q,b).map((z,i)=>sub(z,scale(b[i],value)))));
    if(residual>1e-8) throw new Error('Aperture optimisation did not converge');
    return {b,value,residual};
  }
  function liftTransmission(T) {
    // Front ports then rear ports. Reciprocity demands the REVERSE block T^T.
    return matrix(2*N,(i,j)=>i<N?(j<N?c():T[j-N][i]):(j<N?T[i-N][j]:c()));
  }
  function metrics(b,obj) {
    const plot=pattern(b), peak=plot.reduce((p,x)=>x.power>p.power?x:p,plot[0]);
    const outside=plot.filter(x=>Math.abs(Math.sin(x.angle*Math.PI/180)-Math.sin(obj.target*Math.PI/180))>obj.guard);
    const side=Math.max(...outside.map(x=>x.power)), target=arrayPower(b,obj.target);
    return {target,peak,side,sideToTarget:side/Math.max(target,1e-12),meanSide:obj.angles.reduce((s,x)=>s+arrayPower(b,x),0)/obj.angles.length,score:score(obj.Q,b),plot};
  }
  function compare({field='near',incidence=45,range=5,target=0,goal='sidelobes',strength=.5,operation='reflection'}={}) {
    const a=illumination(field,incidence,range), weight=goal==='peak'?0:20*strength, obj=objective(target,weight);
    const phase=phaseOnly(a,obj), desired=goal==='peak'?normalise(steering(target)):largestEigenvector(obj.Q).b;
    const joint=reciprocalMap(a,desired), d=apply(phase.S,a), b=apply(joint.S,a);
    if(score(obj.Q,b)<score(obj.Q,d)-1e-7) throw new Error('Joint solution is worse than the feasible phase-only reference');
    const S_d=operation==='transmission'?liftTransmission(phase.S):phase.S,S_b=operation==='transmission'?liftTransmission(joint.S):joint.S;
    const input=operation==='transmission'?[...a,...a.map(()=>c())]:a;
    const dAll=apply(S_d,input), bAll=apply(S_b,input), output=operation==='transmission'?N:0;
    const dOut=dAll.slice(output,output+N),bOut=bAll.slice(output,output+N);
    return {a,obj,phase,joint,S_d,S_b,input,d:dOut,b:bOut,dMetrics:metrics(dOut,obj),bMetrics:metrics(bOut,obj),operation,field};
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
  const api={N,positions,c,add,sub,mul,scale,conj,abs2,power,normalise,apply,dot,steering,illumination,arrayPower,pattern,scattering,reciprocalMap,objective,score,phaseOnly,largestEigenvector,liftTransmission,metrics,compare,paired,diagnostics};
  if(typeof module!=='undefined'&&module.exports) module.exports=api;else host.BDRISModel=api;
})(typeof window!=='undefined'?window:this);
