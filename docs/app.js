const $=s=>document.querySelector(s); let data;
const fmt=n=>n.toFixed(2);
function show(){
 const s=data.sites.find(x=>x.id===$('#site').value),r=s.change_on_common_support;
 const obs=data.manifest.observations.filter(x=>x.site===s.id);
 $('#status').textContent=r.common_valid_fraction<.85?'观测提示：共同有效覆盖不足 85%，变化仅适用于下列有效交集。':'质量检查：共同有效覆盖达到 85%。';
 $('#metrics').innerHTML=[['前期观测水域',fmt(r.before_km2)+' km²'],['后期观测水域',fmt(r.after_km2)+' km²'],['共同范围净变化',(r.net_km2>0?'+':'')+fmt(r.net_km2)+' km²'],['共同有效覆盖',fmt(r.common_valid_fraction*100)+'%']].map(([a,b])=>`<div class="metric"><span>${a}</span><strong>${b}</strong></div>`).join('');
 $('#panels').innerHTML=obs.map((o,i)=>`<figure><img src="results/${s.id}-${o.period}.svg" alt="${s.name}${o.datetime.slice(0,10)}水域分类图"><figcaption><b>${i?'后期':'前期'} · ${o.datetime.slice(0,10)}</b>有效覆盖 ${fmt(o.valid_fraction*100)}%</figcaption></figure>`).join('')+`<figure><img src="results/${s.id}-change.svg" alt="共同有效范围内的新增与减少水域"><figcaption><b>变化 · 同一范围比较</b>新增 ${fmt(r.gain_km2)} / 减少 ${fmt(r.loss_km2)} km²</figcaption></figure>`;
 $('#sensitivity').innerHTML=s.sensitivity.map(t=>`<tr class="${t.threshold===0?'selected':''}"><td>${t.threshold.toFixed(1)}${t.threshold===0?' · 默认':''}</td><td>${fmt(t.before_km2)}</td><td>${fmt(t.after_km2)}</td><td>${fmt(t.net_km2)}</td></tr>`).join('');
 $('#sources').innerHTML=obs.map(o=>`<div class="source"><b>${o.datetime.slice(0,10)}</b><code>${o.item_id}</code><p>整景云量 ${fmt(o.scene_cloud_percent)}% · 窗口有效 ${fmt(o.valid_fraction*100)}%<br><a href="${o.query}">STAC 查询 ↗</a> · <a href="${o.assets.green.href}">绿光 COG ↗</a> · Otsu 诊断 ${s.otsu_thresholds[o.period].toFixed(3)}</p></div>`).join('');
 $('#geojson').href=`results/${s.id}-change.geojson`;
}
fetch('results/results.json').then(r=>{if(!r.ok)throw Error(r.status);return r.json()}).then(j=>{data=j;show();$('#site').addEventListener('change',show)}).catch(e=>{$('#status').textContent='结果加载失败，请刷新或下载仓库。'+e.message});
