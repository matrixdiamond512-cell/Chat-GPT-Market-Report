(()=>{
'use strict';
const qs=(s,r=document)=>r.querySelector(s);
const fmtDate=s=>String(s||'').replaceAll('-','/');
const pct=v=>`${v>=0?'+':''}${(v*100).toFixed(1)}%`;
const volume=v=>Number(v).toLocaleString('ja-JP');
const weekday=s=>['日','月','火','水','木','金','土'][new Date(`${s}T00:00:00+09:00`).getDay()];
let rows=[];
function levelLabel(v){if(v>=4500)return'非常に多い';if(v>=3500)return'多い';if(v>=2600)return'標準圏';if(v>=2200)return'やや少ない';return'少ない'}
function diffClass(v){return v>0?'up':v<0?'down':'neutral'}
function diffText(v){if(v>=.5)return'急増';if(v>=.15)return'増加';if(v<=-.35)return'急減';if(v<=-.15)return'減少';return'ほぼ横ばい'}
function avgText(v){if(v>=.35)return'20営業日平均を大きく上回る';if(v>=.1)return'20営業日平均を上回る';if(v<=-.25)return'20営業日平均を大きく下回る';if(v<=-.1)return'20営業日平均を下回る';return'20営業日平均並み'}
function dayFactor(r){if(r.gotoBi===true)return r.gotoBiType||'ゴトー日';if(r.gotoBi===false)return'非ゴトー日';return r.gotoBiType||'未入力'}
function metric(label,value,cls='neutral'){return `<article class="metric ${cls}"><b>${label}</b><strong>${value}</strong></article>`}
function callout(title,text){return `<div class="callout"><strong>${title}</strong><p>${text}</p></div>`}
function renderAnalysis(r){
 qs('#summary').innerHTML=[
  metric('分析日',`${fmtDate(r.date)}（${weekday(r.date)}）`),
  metric('スポット出来高',`${volume(r.volume)} 百万ドル`,'neutral'),
  metric('前営業日比',pct(r.dayChange),diffClass(r.dayChange)),
  metric('20営業日平均との差',pct(r.vs20d),diffClass(r.vs20d))
 ].join('');
 const level=levelLabel(r.volume),change=diffText(r.dayChange),avg=avgText(r.vs20d),factor=dayFactor(r);
 qs('#levelAnalysis').innerHTML=callout(level,`出来高は${volume(r.volume)}百万ドルです。絶対水準としては「${level}」に分類されます。`);
 qs('#changeAnalysis').innerHTML=callout(change,`前営業日比は${pct(r.dayChange)}です。参加者の増減は確認できますが、売買方向は価格データと照合して判断します。`);
 qs('#averageAnalysis').innerHTML=callout(avg,`${pct(r.vs20d)}で、${avg}状態です。短期的なイベントや実需集中の有無を確認する必要があります。`);
 qs('#calendarAnalysis').innerHTML=callout(factor, factor==='未入力'?'ゴトー日、月末月初、連休前後、仲値要因はデータ未入力です。推測せず、今後の入力対象として扱います。':`日柄は「${factor}」です。9:55前後の値動きと出来高集中を照合します。`);
 qs('#flowAnalysis').innerHTML='<ul><li>出来高増加＋一方向の価格変動：実需または投機の集中候補</li><li>出来高増加＋往来相場：売買交錯やポジション交換の可能性</li><li>出来高減少＋大幅変動：薄商いによる値飛びに注意</li><li>出来高だけで実需・投機を断定しない</li></ul>';
 qs('#checkAnalysis').innerHTML='<ul><li>東京時間の高値・安値と仲値後の反応</li><li>米日10年金利差</li><li>NYオプションと注文状況</li><li>輸入・輸出企業の実需</li><li>IMM/CFTCと円ショートの偏り</li><li>欧州時間で東京レンジが維持されたか</li></ul>';
 qs('#historyBody').innerHTML=rows.slice().reverse().map(x=>`<tr class="${x.date===r.date?'selected':''}" data-date="${x.date}"><td>${fmtDate(x.date)}（${weekday(x.date)}）</td><td>${volume(x.volume)}</td><td class="${x.dayChange>0?'positive':x.dayChange<0?'negative':''}">${pct(x.dayChange)}</td><td class="${x.vs20d>0?'positive':x.vs20d<0?'negative':''}">${pct(x.vs20d)}</td><td>${dayFactor(x)}</td><td><span class="badge">${levelLabel(x.volume)}・${diffText(x.dayChange)}</span></td></tr>`).join('');
 qs('#historyBody').querySelectorAll('tr[data-date]').forEach(tr=>tr.addEventListener('click',()=>{qs('#dateSelect').value=tr.dataset.date;renderByDate(tr.dataset.date);window.scrollTo({top:0,behavior:'smooth'});}));
}
function renderByDate(date){const r=rows.find(x=>x.date===date)||rows.at(-1);if(!r)return;qs('#dateSelect').value=r.date;renderAnalysis(r);qs('#dataStatus').textContent=`${rows.length}営業日分を収録｜選択中 ${fmtDate(r.date)}`;}
async function init(){try{const res=await fetch(`tokyo-usdjpy-volume.json?v=${Date.now()}`,{cache:'no-store'});if(!res.ok)throw new Error(`HTTP ${res.status}`);rows=await res.json();rows=rows.filter(x=>x&&x.date&&Number.isFinite(Number(x.volume))).sort((a,b)=>a.date.localeCompare(b.date));if(!rows.length)throw new Error('出来高データがありません');qs('#dateSelect').innerHTML=rows.slice().reverse().map(x=>`<option value="${x.date}">${fmtDate(x.date)}（${weekday(x.date)}）</option>`).join('');qs('#dateSelect').addEventListener('change',e=>renderByDate(e.target.value));qs('#latestButton').addEventListener('click',()=>renderByDate(rows.at(-1).date));renderByDate(rows.at(-1).date);}catch(e){qs('#summary').innerHTML=`<div class="error">出来高データを読み込めません：${String(e.message)}</div>`;qs('#dataStatus').textContent='データ取得失敗';}}
window.addEventListener('DOMContentLoaded',init);
})();