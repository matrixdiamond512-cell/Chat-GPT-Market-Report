(()=>{
'use strict';
const $=(s,r=document)=>r.querySelector(s);
const A=v=>Array.isArray(v)?v:(v==null?[]:[v]);
const T=v=>typeof v==='string'?v:(v&&typeof v==='object'?(v.text||v.summary||v.title||v.name||''):'');
const E=v=>String(v??'').replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[c]));
const stamp=r=>new Date(`${r?.date||'1970-01-01'}T${r?.time||'00:00'}:00+09:00`).getTime()||0;
const reportKey=(r,index=0)=>String(r?.id||`${r?.date||'date'}_${r?.time||'time'}_${r?.title||index}`);
const july=A(window.JULY_REPORTS).map(x=>({date:x[0],time:x[1],id:x[2],url:`https://docs.google.com/document/d/${x[2]}`}));
let reports=[];
let currentKey='';
function list(v,limit=8){const x=A(v).map(T).filter(Boolean).slice(0,limit);return x.length?`<ul>${x.map(y=>`<li>${E(y)}</li>`).join('')}</ul>`:'<p class="muted">データがありません。</p>';}
function active(){return reports.find((r,i)=>reportKey(r,i)===currentKey)||reports[0]||null;}
function reportOptions(r){return reports.map((x,i)=>{const key=reportKey(x,i);return `<option value="${E(key)}" ${key===currentKey?'selected':''}>${E(x.title||`${x.date||''} ${x.time||''}`)}</option>`;}).join('');}
function archiveOptions(){let last='';return july.map(x=>{const day=x.date.replaceAll('-','/');const label=day!==last?`${day}　${x.time}`:`　　　　　${x.time}`;last=day;return `<option value="${E(x.url)}">${E(label)}</option>`;}).join('');}
function marketCards(r){return A(r.markets).map(m=>`<article class="safe-card market-card"><div class="market-head"><h3>${E(m.name||'市場')}</h3><b>${E(m.direction||'中立')}</b></div><div class="market-price">${E(m.price||'—')}</div><p>${E(m.shortOutlook||m.material||'—')}</p><div class="reason-grid"><div><strong>買い材料</strong>${list(m.buyReasons,5)}</div><div><strong>売り材料</strong>${list(m.sellReasons,5)}</div></div><div class="market-detail"><strong>崩れる条件</strong><p>${E(m.breakCondition||r.breakConditions||'—')}</p></div></article>`).join('');}
function render(){const r=active();if(!r)return;$('#updatedAt').textContent=`最終更新：${String(r.date||'').replaceAll('-','/')} ${r.time||''}`;$('#dashboard').innerHTML=`
<section class="safe-controls"><label>ダッシュボード表示レポート<select id="reportSelect">${reportOptions(r)}</select></label><div><button type="button" data-action="text">図解テキスト版</button><button type="button" data-action="history">履歴</button></div></section>
<section class="safe-controls archive-controls"><label><span>7月レポート・アーカイブ</span><small>Google Driveで確認できた${july.length}件</small><select id="archiveSelect"><option value="">日付・時刻を選択</option>${archiveOptions()}</select></label><a class="archive-open disabled" id="archiveOpen" href="#" target="_blank" rel="noopener">Googleドキュメントを開く</a></section>
<section class="safe-card hero" id="s0"><span>今日の相場テーマ</span><h1>${E(r.theme||r.title||'マーケットレポート')}</h1><p>${E(r.mainScenario||'')}</p></section>
<section class="safe-grid three"><article class="safe-card"><h2>重要ニュース</h2>${list(r.news)}</article><article class="safe-card"><h2>前回からの変化</h2>${list(r.changes)}</article><article class="safe-card"><h2>材料と値動きの整合性</h2>${list(r.consistency)}</article></section>
<section class="safe-grid two"><article class="safe-card"><h2>クロスアセット資金フロー</h2>${list(r.crossAssetFlow)}</article><article class="safe-card"><h2>需給・ポジション</h2>${list(r.positioning)}</article></section>
<section class="safe-heading" id="s6"><h2>6市場の売買判断材料</h2></section><section class="safe-grid markets">${marketCards(r)}</section>
<section class="safe-grid three" id="s9"><article class="safe-card"><h2>メインシナリオ</h2><p>${E(r.mainScenario||'—')}</p></article><article class="safe-card"><h2>代替シナリオ</h2><p>${E(r.alternativeScenario||'—')}</p></article><article class="safe-card"><h2>崩れる条件</h2><p>${E(r.breakConditions||'—')}</p></article></section>
<section class="safe-card" id="history"><h2>履歴</h2>${list(r.history)}</section>
<dialog id="safeDialog"><div class="dialog-head"><h2>図解テキスト版</h2><button type="button" data-action="close">×</button></div><textarea readonly>${E(buildText(r))}</textarea></dialog>`;}
function buildText(r){return `${r.title||''}\n\n【相場テーマ】\n${r.theme||'—'}\n\n【主導市場】\n${r.leadingMarket||'—'}\n\n【資金フロー】\n${A(r.crossAssetFlow).map(T).join('\n')||'—'}\n\n【需給】\n${A(r.positioning).map(T).join('\n')||'—'}\n\n【メインシナリオ】\n${r.mainScenario||'—'}\n\n【代替シナリオ】\n${r.alternativeScenario||'—'}\n\n【崩れる条件】\n${r.breakConditions||'—'}`;}
async function init(){try{const res=await fetch(`reports.json?safe=${Date.now()}`,{cache:'no-store'});if(!res.ok)throw new Error(`HTTP ${res.status}`);const json=await res.json();reports=(Array.isArray(json)?json:A(json.reports)).sort((a,b)=>stamp(b)-stamp(a));if(!reports.length)throw new Error('レポートがありません');currentKey=reportKey(reports[0],0);render();}catch(err){$('#dashboard').innerHTML=`<div class="safe-error">ダッシュボードを読み込めません。${E(err.message)}</div>`;$('#updatedAt').textContent='データ取得失敗';}}
document.addEventListener('change',e=>{if(e.target?.id==='reportSelect'){currentKey=e.target.value;render();return;}if(e.target?.id==='archiveSelect'){const a=$('#archiveOpen');const url=e.target.value;if(!a)return;a.href=url||'#';a.classList.toggle('disabled',!url);}});
document.addEventListener('click',e=>{const archive=e.target.closest('#archiveOpen');if(archive?.classList.contains('disabled')){e.preventDefault();return;}const btn=e.target.closest('[data-action]');if(!btn)return;const action=btn.dataset.action;if(action==='text')$('#safeDialog')?.showModal();if(action==='close')$('#safeDialog')?.close();if(action==='history')$('#history')?.scrollIntoView({behavior:'smooth'});});
init();
})();