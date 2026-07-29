(()=>{'use strict';
const A=v=>Array.isArray(v)?v:(v==null?[]:[v]);
const E=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const T=v=>typeof v==='string'?v:(v?.text||v?.summary||v?.value||v?.label||'');
const stamp=r=>new Date(`${r?.date||'1970-01-01'}T${r?.time||'00:00'}:00+09:00`).getTime()||0;
let reports=[],report=null,lastKey='';
function selectedId(){return document.querySelector('#reportSelect')?.value||''}
function choose(){const id=selectedId();report=(id&&reports.find(r=>String(r.id)===String(id)))||reports[0]||null;return report}
function getPath(o,paths){for(const p of paths){let v=o;for(const k of p.split('.'))v=v?.[k];if(v!==undefined&&v!==null&&T(v)!=='')return v}return null}
function pct(v){const s=T(v).trim();if(!s)return'';return /%/.test(s)?s:`${s}%`}
function field(r,paths){const v=getPath(r,paths);return v==null?'':T(v).trim()}
function volumeData(r){const block=getPath(r,['usdjpyVolume','usdJpyVolume','fxVolume.usdjpy','volumeAnalysis.usdjpy','tokyoUsdJpyVolume'])||{};
 const volume=field(block,['spotVolume','volume','previousBusinessDayVolume','tokyoSpotVolume'])||field(r,['usdjpySpotVolume','usdJpySpotVolume','tokyoUsdJpySpotVolume']);
 const day=field(block,['dayChange','change','previousDayChange','volumeDayChange'])||field(r,['usdjpyVolumeDayChange','usdJpyVolumeDayChange']);
 const avg=field(block,['vs20DayAverage','twentyDayAverageDiff','diff20d','volume20DayDiff'])||field(r,['usdjpyVolume20DayDiff','usdJpyVolume20DayDiff']);
 const goto=field(block,['gotoDay','calendarFactor','dayFactor'])||field(r,['gotoDay','usdjpyGotoDay']);
 const interpretation=field(block,['interpretation','analysis','commentary','meaning'])||field(r,['usdjpyVolumeAnalysis','usdJpyVolumeAnalysis']);
 const flow=field(block,['flow','flowAssessment','directionAssessment','demandAssessment'])||field(r,['usdjpyFlowAssessment','usdJpyFlowAssessment']);
 const drivers=A(getPath(block,['drivers','factors','evidence'])).map(T).filter(Boolean);
 const asOf=field(block,['asOf','date','referenceDate'])||field(r,['usdjpyVolumeAsOf']);
 return{volume,day,avg,goto,interpretation,flow,drivers,asOf}}
function missing(label){return `取得不能（${label}が構造化データに未収録）`}
function metric(label,value,cls=''){return `<div class="fx-volume-metric ${cls}"><b>${label}</b><span>${E(value)}</span></div>`}
function render(r){const dash=document.querySelector('#dashboard');if(!dash)return;const d=volumeData(r),key=JSON.stringify([r?.id,r?.date,r?.time,d]);if(key===lastKey&&document.querySelector('#usdjpy-volume-analysis'))return;document.querySelector('#usdjpy-volume-analysis')?.remove();
 const html=`<section id="usdjpy-volume-analysis" class="fx-volume-section" data-report-id="${E(r?.id||'')}"><div class="section-heading fx-volume-heading"><div><span>USD/JPY FLOW & VOLUME</span><h2>東京市場USD/JPY出来高分析</h2></div><p>${E(d.asOf?`基準日：${d.asOf}`:'選択中レポートに連動')}</p></div><div class="fx-volume-card"><div class="fx-volume-metrics">${metric('前営業日スポット出来高',d.volume?`${d.volume}${/百万ドル|million|USD/i.test(d.volume)?'':' 百万ドル'}`:missing('前営業日スポット出来高'))}${metric('前営業日比',d.day?pct(d.day):missing('前営業日比'),/^\s*-/.test(d.day)?'down':'up')}${metric('20営業日平均との差',d.avg?pct(d.avg):missing('20営業日平均との差'),/^\s*-/.test(d.avg)?'down':'up')}${metric('日柄要因',d.goto||missing('ゴトー日・月末月初等の日柄要因'))}</div><div class="fx-volume-analysis-grid"><article><b>出来高の解釈</b><p>${E(d.interpretation||missing('出来高の解釈'))}</p></article><article><b>方向判断との組み合わせ</b><p>${E(d.flow||missing('実需・オプション・金利差を含む方向判断'))}</p></article></div>${d.drivers.length?`<div class="fx-volume-drivers"><b>確認材料</b>${d.drivers.map(x=>`<span>${E(x)}</span>`).join('')}</div>`:''}<p class="fx-volume-note">出来高だけでUSD/JPYの方向を断定せず、仲値・実需、NYオプション、注文情報、米日金利差、IMM/CFTC、原油輸入に伴うドル需要と合わせて判断します。</p></div></section>`;
 const anchor=dash.querySelector('#s5')||dash.querySelector('#s6')||dash.querySelector('.causal-section');
 if(anchor)anchor.insertAdjacentHTML('afterend',html);else dash.insertAdjacentHTML('beforeend',html);lastKey=key}
async function load(){try{const res=await fetch(`reports.json?fxvol=${Date.now()}`,{cache:'no-store'});if(!res.ok)throw Error('reports.json');const j=await res.json();reports=(Array.isArray(j)?j:A(j.reports)).sort((a,b)=>stamp(b)-stamp(a));choose();if(report)render(report)}catch(e){console.error('USDJPY volume analysis:',e)}}
document.addEventListener('change',e=>{if(e.target?.id==='reportSelect'){choose();if(report)render(report)}});
const obs=new MutationObserver(()=>{if(!reports.length)return;choose();if(report)render(report)});obs.observe(document.documentElement,{childList:true,subtree:true});
window.addEventListener('DOMContentLoaded',()=>{load();setInterval(load,300000)});
})();