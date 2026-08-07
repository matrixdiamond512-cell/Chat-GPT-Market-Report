(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');if(!root)return;
const num=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const fmt=(v,d=0)=>Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
function card(re){return [...root.querySelectorAll('.nikkei-card')].find(x=>re.test(x.querySelector('.nikkei-section-title')?.textContent||''));}
function apply(d){
 const spot=d.spot||{}, fut=d.futures||{}, opt=d.options||{};
 if(opt.ivStatus==='verified'&&num(opt.iv)!==null){
  const summary=[...root.querySelectorAll('.nikkei-summary')].find(x=>/オプション需給/.test(x.querySelector('.nikkei-summary-label')?.textContent||''));
  if(summary){const v=summary.querySelector('.nikkei-summary-value'),s=summary.querySelector('.nikkei-summary-sub');if(v)v.textContent=`基準IV ${fmt(opt.iv,1)}%`;if(s)s.textContent=`JPX ${date(opt.ivAsOfDate)} / SQまで ${Number.isFinite(Number(opt.businessDaysToSq))?fmt(opt.businessDaysToSq,0):'—'}営業日`;}
 }
 const basisCard=card(/^3\. /);
 if(basisCard&&spot.status==='verified'&&fut.status==='verified'){
  const title=basisCard.querySelector('.nikkei-section-title');if(title)title.textContent='3. 現物終値 vs 先物（単純差）';
  const items=basisCard.querySelectorAll('.nikkei-basis-item');
  const same=spot.asOfDate&&fut.asOfDate&&String(spot.asOfDate).slice(0,10)===String(fut.asOfDate).slice(0,10);
  const sv=num(spot.value),fv=num(fut.price),diff=same&&sv!==null&&fv!==null?fv-sv:null;
  if(items.length>=3){
   const l0=items[0].querySelector('.nikkei-basis-label'),v0=items[0].querySelector('.nikkei-basis-value'),n0=items[0].querySelector('.nikkei-note');if(l0)l0.textContent='日経225現物終値';if(v0&&sv!==null)v0.textContent=fmt(sv,2);if(n0)n0.textContent=`基準日 ${date(spot.asOfDate)}`;
   const l1=items[1].querySelector('.nikkei-basis-label'),v1=items[1].querySelector('.nikkei-basis-value'),n1=items[1].querySelector('.nikkei-note');if(l1)l1.textContent='日経225先物（期近）';if(v1&&fv!==null)v1.textContent=fmt(fv,0);if(n1)n1.textContent=`基準日 ${date(fut.asOfDate)}`;
   const l2=items[2].querySelector('.nikkei-basis-label'),v2=items[2].querySelector('.nikkei-basis-value'),n2=items[2].querySelector('.nikkei-note');if(l2)l2.textContent='現物終値対比差';if(v2)v2.textContent=diff===null?'基準日不一致':`${diff>0?'+':''}${fmt(diff,2)}円`;if(n2)n2.textContent=diff===null?'同一基準日のみ計算':'先物－現物終値';
  }
  const notes=basisCard.querySelectorAll('.nikkei-note');const last=notes[notes.length-1];if(last)last.textContent=same?'同一取引日の比較ですが、現物終値と先物の取得時刻は異なります。理論ベーシスではなく、海外時間のギャップ把握用の単純差です。':'現物と先物の基準日が一致しないため差を計算しません。';
 }
 const optCard=card(/^5\. /);
 if(optCard){
  const minis=optCard.querySelectorAll('.nikkei-mini-card');
  if(minis.length>=3&&opt.ivStatus==='verified'&&num(opt.iv)!==null){const lab=minis[2].querySelector('.nikkei-mini-label'),val=minis[2].querySelector('.nikkei-mini-value'),note=minis[2].querySelector('.nikkei-note');if(lab)lab.textContent='JPX基準IV';if(val)val.textContent=`${fmt(opt.iv,2)}%`;if(note)note.textContent=`${date(opt.ivAsOfDate)} / 期近 ${opt.ivContractMonth||'—'}`;}
  if(minis.length>=2&&opt.putCallStatus==='unavailable'){const val=minis[1].querySelector('.nikkei-mini-value'),note=minis[1].querySelector('.nikkei-note');if(val)val.textContent='取得不能';if(note)note.textContent='現在のJPX当日総括にはNK225E行なし';}
  const callout=optCard.querySelector('.nikkei-callout');if(callout&&opt.ivStatus==='verified')callout.textContent=`JPX基準ボラティリティ ${fmt(opt.iv,2)}%。Put/Callは${opt.putCallStatus==='verified'?'取得済み':'取得不能'}。SQ・IV・Put/Callを別々に鮮度管理します。`;
 }
}
fetch('data/nikkei225-supply-demand.json',{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject()).then(d=>{let n=0;const t=setInterval(()=>{apply(d);if(root.querySelector('.nikkei-section-title')||++n>50)clearInterval(t)},100);apply(d)}).catch(()=>{});
})();
