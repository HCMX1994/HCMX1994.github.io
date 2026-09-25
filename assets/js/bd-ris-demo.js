/* Compact UI for the separately tested lossless BD-RIS model. */
(function () {
  'use strict';
  const root=document.getElementById('bd-lab');if(!root)return;
  const M=window.BDRISModel, find=s=>root.querySelector(s), all=s=>root.querySelectorAll(s), motion=matchMedia('(prefers-reduced-motion: reduce)');
  const state={example:'compare',field:'near',incidence:45,range:5,target:0,goal:'sidelobes',strength:.5,reflected:-25,transmitted:30,share:.5,playing:!motion.matches};
  let comparison,pair,frame=0,queued=0,last=null,time=0,visible=true;
  const ns='http://www.w3.org/2000/svg', cy=147, radius=db=>138*Math.max(0,Math.min(1,(db+30)/30));
  const peak=plot=>plot.reduce((p,x)=>x.power>p.power?x:p,plot[0]);
  function element(tag,attrs,parent,text) {const node=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))node.setAttribute(k,v);if(text!==undefined)node.textContent=text;parent.appendChild(node);return node;}
  function point(angle,r,side,cx=240) {const t=angle*Math.PI/180;return [cx+side*r*Math.cos(t),cy+r*Math.sin(t)];}
  function lobe(plot,side,cx=240) {return `M${cx},${cy}`+plot.map(p=>` L${point(p.angle,radius(p.db),side,cx).map(x=>x.toFixed(2)).join(',')}`).join('')+' Z';}
  function line(angle,side,r=141,cx=240) {return `M${cx},${cy} L${point(angle,r,side,cx).join(',')}`;}
  function grid(parent,side,cx=240,labels=true) {
    for(const r of [46,92,138])element('path',{d:`M${cx},${cy-r} A${r},${r} 0 0 ${side<0?0:1} ${cx},${cy+r}`,class:'bd-v3-ring'},parent);
    for(const angle of [-45,0,45]) {
      element('path',{d:line(angle,side,138,cx),class:'bd-v3-axis'},parent);
      if(labels){const p=point(angle,155,side,cx);element('text',{x:p[0],y:p[1]+4,'text-anchor':'middle',class:'bd-v3-angle'},parent,`${angle>0?'+':''}${angle}°`);}
    }
  }
  function antennas(parent,transmission=false) {
    parent.replaceChildren();
    for(let i=0;i<M.N;i++) {
      const spacing=190/(M.N-1),y=cy-95+i*spacing;
      if(transmission) {element('line',{x1:228,y1:y,x2:252,y2:y,class:'bd-v3-link'},parent);element('rect',{x:248,y:y-1.7,width:5,height:3.4,class:'bd-v3-rear'},parent);}
      else if(i%2===0)element('path',{d:`M243,${y} H250 V${y+spacing} H243`,class:'bd-v3-link',fill:'none'},parent);
      element('rect',{x:transmission?227:237,y:y-1.7,width:6,height:3.4,class:'bd-v3-port'},parent);
    }
  }
  const matrixD=find('.bd-matrix-d'),matrixB=find('.bd-matrix-b');
  function matrixDisplay(parent,S) {
    parent.replaceChildren();
    parent.style.gridTemplateColumns=`repeat(${S.length},1fr)`;
    for(let i=0;i<M.N;i++)for(let j=0;j<M.N;j++){
      const z=S[i][j],span=document.createElement('span'),text=`Row ${i+1}, column ${j+1}: ${z.re.toFixed(4)} ${z.im<0?'−':'+'} ${Math.abs(z.im).toFixed(4)}j; magnitude ${Math.sqrt(M.abs2(z)).toFixed(4)}`;
      span.style.background=`rgba(125,51,69,${Math.min(1,Math.sqrt(M.abs2(z)))})`;span.title=text;span.tabIndex=0;span.setAttribute('aria-label',text);parent.appendChild(span);
    }
  }
  function formatMatrix(S) {return S.map(row=>row.map(z=>`${z.re.toFixed(3)}${z.im<0?'−':'+'}${Math.abs(z.im).toFixed(3)}j`).join('  ')).join('\n');}
  const db=(p,digits=1)=>{const value=10*Math.log10(Math.max(p,1e-12));return `${(Math.abs(value)<.5*10**(-digits)?0:value).toFixed(digits)} dB`;};
  function validate(S,a) {const d=M.diagnostics(S,a);if(Math.max(...Object.values(d))>1e-8)throw new Error('Scattering matrix failed the reciprocal/lossless checks');return d;}
  function updateMatrices() {
    if(!comparison||!find('.bd-comparison-details').open)return;
    matrixDisplay(matrixD,comparison.S_d);matrixDisplay(matrixB,comparison.S_b);
    find('.bd-d-matrix-title').textContent='D-RIS · 36 × 36 R';find('.bd-b-matrix-title').textContent='BD-RIS · 18 two-port blocks';
    find('.bd-matrix-values').textContent=`36 reflecting ports; adjacent groups [1,2], [3,4], …, [35,36]\n\nD-RIS:\n${formatMatrix(comparison.S_d)}\n\nBD-RIS:\n${formatMatrix(comparison.S_b)}`;
  }
  function updateCompare() {
    comparison=M.compare(state);validate(comparison.S_d,comparison.input);validate(comparison.S_b,comparison.input);
    const side=-1,g=find('.bd-grid');g.replaceChildren();grid(g,side);
    antennas(find('.bd-antenna-drawing'));
    find('.bd-main-b').setAttribute('d',lobe(comparison.bMetrics.plot,side));find('.bd-main-d').setAttribute('d',lobe(comparison.dMetrics.plot,side));
    find('.bd-main-target').setAttribute('d',line(state.target,side));
    for(const [selector,sign]of [['.bd-guard-left',-1],['.bd-guard-right',1]]) {
      const u=Math.sin(state.target*Math.PI/180)+sign*comparison.obj.guard,node=find(selector);node.style.display=state.goal==='sidelobes'&&Math.abs(u)<1?'':'none';if(Math.abs(u)<1)node.setAttribute('d',line(Math.asin(u)*180/Math.PI,side));
    }
    const name='D-RIS';all('.bd-d-name').forEach(n=>n.textContent=name);
    find('.bd-mode-label').textContent='Reflection';
    find('.bd-network-label').textContent='BD: 36 ports · 18 groups · group size 2';
    find('.bd-suppression').hidden=state.goal!=='sidelobes';
    find('#bd-target-value').textContent=`${state.target}°`;find('#bd-strength-value').textContent=state.strength<.3?'Gentle':state.strength>.7?'Strong':'Balanced';
    const d=comparison.dMetrics,b=comparison.bMetrics;
    const targetTradeoff=b.target<d.target-1e-6?', with a trade-off in target power.':b.target>d.target+1e-6?'; target power also improves in this case.':', at similar target power.';
    find('.bd-brief').textContent=state.goal==='peak'?(Math.abs(b.target-d.target)<1e-7?'Equal target power here: phase alignment already reaches the common bound.':b.target/d.target<1.01?'Nearly equal target power: amplitudes within each adjacent pair differ only slightly. The small BD improvement is shown in the details.':'BD-RIS redistributes input power within each pair to increase power at the target.'):(b.meanSide<d.meanSide-1e-7?`BD-RIS lowers mean sidelobe-region power${targetTradeoff}`:'Compare the same target-power / sidelobe-region trade-off; extra freedom does not improve every metric.');
    find('.bd-comparison-condition').textContent='Both designs use the same 36 reflecting ports in a half-wavelength-spaced linear array. D-RIS has 36 independent one-port loads. BD-RIS has 18 adjacent two-port groups: [1,2], [3,4], …, [35,36]. Each block is symmetric and unitary; no power transfers between groups.';
    for(const [key,values]of [['d',d],['b',b]]){find(`[data-result="${key}-target"]`).textContent=db(values.target,3);find(`[data-result="${key}-side"]`).textContent=db(values.sideToTarget);find(`[data-result="${key}-score"]`).textContent=values.score.toFixed(4);find(`[data-result="${key}-direction"]`).textContent=`${values.peak.angle.toFixed(2)}°`;}
    find('.bd-model-health').textContent='Reciprocity, lossless power conservation and S-to-output consistency checked for this state. Each two-port group preserves its own input power.';
    updateMatrices();
    find('.bd-compare-plot').setAttribute('aria-label',`${state.field}-field illumination; reflection; 36 ports in 18 adjacent pairs; target ${state.target} degrees. Dashed ${name} and solid BD-RIS use a common power scale and objective.`);
  }
  function updatePairs() {
    pair=M.paired(state);validate(pair.S,pair.a);
    find('.bd-pair-r').setAttribute('d',lobe(pair.rPattern,-1,226));find('.bd-pair-t').setAttribute('d',lobe(pair.tPattern,1,254));
    find('.bd-pair-r').style.display=find('.bd-flow-r').style.display=state.share===1?'none':'';
    find('.bd-pair-t').style.display=find('.bd-flow-t').style.display=state.share===0?'none':'';
    for(const [key,value]of [['reflected',state.reflected],['transmitted',state.transmitted]])find(`#bd-${key}-value`).textContent=`${value}°`;
    find('#bd-share-value').textContent=`${Math.round(100*state.share)}%`;
    find('#bd-reflected').disabled=state.share===1;find('#bd-transmitted').disabled=state.share===0;
    const mode=state.share===0?'reflection':state.share===1?'transmission':'hybrid';all('[data-pair-mode]').forEach(n=>n.setAttribute('aria-pressed',String(n.dataset.pairMode===mode)));
    find('.bd-pair-brief').textContent=`${Math.round(100*pair.rPower)}% front / ${Math.round(100*pair.tPower)}% rear port power. Each pair conserves power; structural scattering is omitted.`;
  }
  function update() {
    try {
      if(!M)throw new Error('The model script did not load');
      find('.bd-error').hidden=true;find('.bd-compare-panel').hidden=state.example!=='compare';find('.bd-pairs-panel').hidden=state.example!=='pairs';
      all('[data-field]').forEach(n=>n.setAttribute('aria-pressed',String(n.dataset.field===state.field)));all('[data-example]').forEach(n=>n.setAttribute('aria-pressed',String(n.dataset.example===state.example)));
      find('.bd-source-note').innerHTML=state.field==='near'?'<span aria-hidden="true">◔</span> Spherical illumination · amplitude + phase vary':'<span aria-hidden="true">≋</span> Plane-wave illumination · equal amplitudes';
      find('.bd-range-control').hidden=state.field!=='near';find('#bd-incidence-value').textContent=`${state.incidence}°`;find('#bd-range-value').textContent=`${state.range} λ`;
      if(state.example==='compare')updateCompare();else updatePairs();
      find('.bd-compare-plot').style.visibility='';find('.bd-pair-plot').style.visibility='';draw();
    } catch(error) {
      find('.bd-error').hidden=false;find('.bd-error').textContent='This setting could not be validated. Change a control or reload to retry.';find('.bd-compare-plot').style.visibility='hidden';find('.bd-pair-plot').style.visibility='hidden';console.error(error);
    }
  }
  function requestUpdate(){if(queued)cancelAnimationFrame(queued);queued=requestAnimationFrame(()=>{queued=0;update();});}
  function dot(selector,plot,side,cx,offset=0){const p=peak(plot),xy=point(p.angle,radius(p.db)*((time*.3+offset)%1),side,cx),node=find(selector);node.setAttribute('cx',xy[0]);node.setAttribute('cy',xy[1]);}
  function draw(){if(state.example==='compare'&&comparison){dot('.bd-flow-b',comparison.bMetrics.plot,-1,240);dot('.bd-flow-d',comparison.dMetrics.plot,-1,240,.4);}else if(pair){dot('.bd-flow-r',pair.rPattern,-1,226);dot('.bd-flow-t',pair.tPattern,1,254,.4);}}
  function animate(now){frame=0;if(!state.playing||!visible||document.hidden){last=null;return;}if(last!==null)time+=Math.min((now-last)/1000,.1);last=now;draw();frame=requestAnimationFrame(animate);}
  function playback(){if(frame)cancelAnimationFrame(frame);last=null;frame=0;all('.bd-play').forEach(n=>{n.textContent=state.playing?'Pause':'Play';n.setAttribute('aria-label',`${state.playing?'Pause':'Play'} direction markers`);});if(state.playing&&visible&&!document.hidden)frame=requestAnimationFrame(animate);}
  all('[data-example]').forEach(n=>n.addEventListener('click',()=>{state.example=n.dataset.example;update();}));
  all('[data-field]').forEach(n=>n.addEventListener('click',()=>{state.field=n.dataset.field;update();}));
  find('#bd-goal').addEventListener('change',event=>{state.goal=event.target.value;update();});
  find('.bd-comparison-details').addEventListener('toggle',updateMatrices);
  for(const key of ['target','strength','incidence','range','reflected','transmitted','share'])find(`#bd-${key}`).addEventListener('input',event=>{state[key]=Number(event.target.value);requestUpdate();});
  all('[data-pair-mode]').forEach(n=>n.addEventListener('click',()=>{state.share={reflection:0,transmission:1,hybrid:.5}[n.dataset.pairMode];find('#bd-share').value=state.share;update();}));
  all('.bd-play').forEach(n=>n.addEventListener('click',()=>{state.playing=!state.playing;playback();}));
  document.addEventListener('visibilitychange',playback);motion.addEventListener('change',()=>{state.playing=!motion.matches;playback();});new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;playback();}).observe(root);
  const pairedGrid=find('.bd-pair-grid');grid(pairedGrid,-1,226,false);grid(pairedGrid,1,254,false);antennas(find('.bd-pair-antennas'),true);
  find('.bd-controls').hidden=false;find('.bd-fallback').hidden=true;update();playback();
})();
