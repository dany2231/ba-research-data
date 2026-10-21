(()=>{
  // sensortower-data.js가 없으면(공개 사이트 등) 아무것도 표시하지 않습니다.
  const data=window.SENSORTOWER_DATA;
  window.SensorTowerOverlay={mount(){}};
  if(!data||!data.monthly)return;
  const countries=Object.keys(data.countries||{}).filter(c=>data.monthly[c]);
  if(!countries.length)return;
  const metrics={revenue:{label:'매출',color:'#d9480f',fmt:v=>'$'+(v>=1e6?(v/1e6).toFixed(1)+'M':Math.round(v/1e3)+'K')},downloads:{label:'다운로드',color:'#0b7285',fmt:v=>v>=1e4?(v/1e4).toFixed(1)+'만':v.toLocaleString()}};
  const state={metric:'',country:countries[0]};
  document.head.insertAdjacentHTML('beforeend',`<style>
.stSwitch{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:0 0 14px;padding:11px 12px;background:#fff6ef;border-radius:10px}.stSwitch strong{font-size:12px;margin-right:3px}.stSwitch button{font:inherit;font-size:11px;color:#647089;background:#fff;border:1px solid #dce4f0;border-radius:8px;padding:7px 10px;cursor:pointer}.stSwitch button.on{color:#fff;background:#12213d;border-color:#12213d}.stSwitch .sep{width:1px;height:20px;background:#e3d6cc;margin:0 4px}.stSwitch small{color:#8a7a6d;font-size:10px;margin-left:auto}
.stLayer{position:absolute;inset:0;pointer-events:none;z-index:4}.stLayer svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}.stDot{position:absolute;width:9px;height:9px;margin:-4.5px 0 0 -4.5px;border-radius:50%;border:2px solid #fff;pointer-events:auto;cursor:default}.stDot.partial{background:#fff!important;border-color:currentColor}.stAxis{position:absolute;right:-46px;top:0;bottom:0;width:42px;display:flex;flex-direction:column;justify-content:space-between;font-size:10px;font-weight:700}
.scroll:has(.stLayer) .chart{grid-template-columns:38px 1fr 48px}
</style>`);
  // 키는 'YYYY-MM' 또는 'YYYY-Qn'입니다. 분기는 원본에 있는 월만 합산하고, 빠진 월이 있으면 부분 집계로 표시합니다.
  function value(key){const months=data.monthly[state.country];let ms=[key];const q=key.match(/^(\d{4})-Q([1-4])$/);if(q)ms=[1,2,3].map(i=>`${q[1]}-${String((q[2]-1)*3+i).padStart(2,'0')}`);const found=ms.filter(m=>months[m]);if(!found.length)return null;return{v:found.reduce((s,m)=>s+months[m][state.metric],0),partial:found.length<ms.length,months:found.map(m=>months[m])}}
  function draw(opts){const plot=opts.plot;plot.querySelector('.stLayer')?.remove();if(!state.metric)return;const keys=opts.keys(),pts=keys.map(value),max=Math.max(...pts.map(p=>p?p.v:0));if(!max)return;const m=metrics[state.metric],top=max*1.08,n=keys.length,layer=document.createElement('div');layer.className='stLayer';layer.style.color=m.color;
    const xy=(p,i)=>[(i+.5)/n*100,100-p.v/top*100];let path='',open=false;pts.forEach((p,i)=>{if(!p){open=false;return}const [x,y]=xy(p,i);path+=`${open?'L':'M'}${x} ${y}`;open=true});
    layer.innerHTML=`<svg viewBox="0 0 100 100" preserveAspectRatio="none"><path d="${path}" fill="none" stroke="${m.color}" stroke-width="2.2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg><div class="stAxis">${[1,.75,.5,.25,0].map(f=>`<span>${f?m.fmt(top*f):0}</span>`).join('')}</div>`+pts.map((p,i)=>{if(!p)return'';const [x,y]=xy(p,i);return`<span class="stDot${p.partial?' partial':''}" data-i="${i}" style="left:${x}%;top:${y}%;background:${m.color}"></span>`}).join('');
    plot.append(layer);const tip=document.querySelector('#tip');layer.querySelectorAll('.stDot').forEach(d=>{const i=+d.dataset.i,p=pts[i];d.onmousemove=e=>{e.stopPropagation();const plat={};p.months.forEach(r=>Object.entries(r.platforms||{}).forEach(([k,v])=>plat[k]=(plat[k]||0)+v[state.metric]));tip.innerHTML=`<b>${keys[i]} · ${data.countries[state.country]} ${m.label}</b><br>${m.fmt(p.v)}`+Object.entries(plat).map(([k,v])=>`<br>${k==='ios'?'iOS':'Android'}: ${m.fmt(v)}`).join('')+(p.partial?'<br>일부 월만 포함':'')+`<br><span style="opacity:.7">${data.source}</span>`;tip.style.left=e.clientX+'px';tip.style.top=e.clientY+'px';tip.style.opacity=1};d.onmouseleave=()=>tip.style.opacity=0})}
  // opts: {before: 스위치를 넣을 요소, plot: 막대 차트 영역, keys: 현재 표시 중인 기간 키 배열을 돌려주는 함수}
  window.SensorTowerOverlay.mount=function(opts){const box=document.createElement('div');box.className='stSwitch';box.innerHTML='<strong>Sensor Tower</strong>'+[['','끄기'],...Object.entries(metrics).map(([k,v])=>[k,v.label])].map(([k,l])=>`<button data-st-metric="${k}" class="${k===state.metric?'on':''}">${l}</button>`).join('')+'<span class="sep"></span>'+countries.map(c=>`<button data-st-country="${c}" class="${c===state.country?'on':''}">${data.countries[c]}</button>`).join('')+`<small>${data.source} · ${data.range.join('~')} · 갱신 ${data.fetchedAt.slice(0,10)}</small>`;opts.before.before(box);
    const redraw=()=>draw(opts);box.querySelectorAll('button').forEach(b=>b.onclick=()=>{if(b.dataset.stCountry)state.country=b.dataset.stCountry;else state.metric=b.dataset.stMetric;box.querySelectorAll(b.dataset.stCountry?'[data-st-country]':'[data-st-metric]').forEach(x=>x.classList.toggle('on',x===b));redraw()});
    // 페이지가 차트를 다시 그리면 plot 내용이 교체되므로 그때마다 선을 다시 얹습니다.
    new MutationObserver(()=>{if(state.metric&&!opts.plot.querySelector('.stLayer'))redraw()}).observe(opts.plot,{childList:true});redraw()};
})();
