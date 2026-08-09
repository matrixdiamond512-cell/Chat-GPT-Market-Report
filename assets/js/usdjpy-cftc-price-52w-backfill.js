(()=>{
'use strict';
const PRICE_52=[
['2025-08-12',147.80],['2025-08-19',147.61],['2025-08-26',147.43],['2025-09-02',148.35],
['2025-09-09',147.41],['2025-09-16',146.48],['2025-09-23',147.62],['2025-09-30',147.89],
['2025-10-07',151.84],['2025-10-14',151.80],['2025-10-21',151.87],['2025-10-28',152.14],
['2025-11-04',153.67],['2025-11-11',154.16],['2025-11-18',155.52],['2025-11-25',156.11],
['2025-12-02',155.85],['2025-12-09',156.86],['2025-12-16',154.77],['2025-12-23',156.15],
['2025-12-30',156.40],['2026-01-06',156.66],['2026-01-13',159.14],['2026-01-20',158.18],
['2026-01-27',152.59],['2026-02-03',155.84],['2026-02-10',154.50],['2026-02-17',153.26],
['2026-02-24',155.86],['2026-03-03',157.64],['2026-03-10',158.14],['2026-03-17',158.95],
['2026-03-24',158.69],['2026-03-31',158.75],['2026-04-07',159.45],['2026-04-14',158.80],
['2026-04-21',159.41],['2026-04-28',159.60],['2026-05-05',157.87],['2026-05-12',157.61],
['2026-05-19',159.09],['2026-05-26',159.29],['2026-06-02',159.92],['2026-06-09',160.37],
['2026-06-16',160.42],['2026-06-23',161.57],['2026-06-30',162.62],['2026-07-07',162.14],
['2026-07-14',162.23],['2026-07-21',163.19],['2026-07-28',163.85],['2026-08-04',157.76]
];
const NS='http://www.w3.org/2000/svg';
const W=1120,H=420,L=82,R=88,T=32,B=58,pw=W-L-R,ph=H-T-B;
const x=i=>L+i*pw/(PRICE_52.length-1);
const yScale=(v,min,max)=>T+(max-v)/(max-min)*ph;
function activeWeeks(){
 const b52=document.querySelector('.usd-position-range button[data-weeks="52"]');
 if(b52)return b52.classList.contains('is-active')?52:26;
 const badge=document.getElementById('usdjpy-positioning-frequency');
 return badge&&/52週/.test(badge.textContent||'')?52:26;
}
function restoreOriginal(svg){
 svg.querySelectorAll('[data-original-usdjpy-price="1"]').forEach(el=>{el.style.display='';delete el.dataset.originalUsdjpyPrice;});
 svg.querySelectorAll('[data-original-usdjpy-axis="1"]').forEach(el=>{el.style.display='';delete el.dataset.originalUsdjpyAxis;});
 svg.querySelectorAll('[data-full-usdjpy-price="1"]').forEach(el=>el.remove());
}
function el(name,attrs={}){const e=document.createElementNS(NS,name);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));return e;}
function patch(){
 const target=document.getElementById('usdjpy-positioning-content');
 const svg=target?.querySelector('svg.usd-position-svg');
 if(!svg)return;
 if(activeWeeks()!==52){restoreOriginal(svg);return;}
 if(svg.querySelector('[data-full-usdjpy-price="1"]'))return;
 svg.querySelectorAll('.line-price,.dot-price').forEach(node=>{if(!node.hasAttribute('data-full-usdjpy-price')){node.dataset.originalUsdjpyPrice='1';node.style.display='none';}});
 svg.querySelectorAll('text.axis-label').forEach(node=>{
   const xv=Number(node.getAttribute('x'));
   if(Number.isFinite(xv)&&xv>=W-R+8&&!node.hasAttribute('data-full-usdjpy-price')){node.dataset.originalUsdjpyAxis='1';node.style.display='none';}
 });
 const prices=PRICE_52.map(r=>r[1]);
 let pmin=Math.min(...prices),pmax=Math.max(...prices);const span=pmax-pmin||1;pmin-=span*.08;pmax+=span*.08;
 const g=el('g',{'data-full-usdjpy-price':'1'});
 const pts=PRICE_52.map((r,i)=>`${x(i)},${yScale(r[1],pmin,pmax)}`);
 g.appendChild(el('polyline',{points:pts.join(' '),class:'line-price','data-full-usdjpy-price':'1'}));
 PRICE_52.forEach((r,i)=>g.appendChild(el('circle',{cx:x(i),cy:yScale(r[1],pmin,pmax),r:1.9,class:'dot-price','data-full-usdjpy-price':'1'})));
 for(let i=0;i<=2;i++){
   const v=pmin+(pmax-pmin)*i/2;const yy=T+ph-i*ph/2;
   const t=el('text',{x:W-R+10,y:yy+4,class:'axis-label','data-full-usdjpy-price':'1'});t.textContent=v.toFixed(1);g.appendChild(t);
 }
 svg.appendChild(g);
 const legend=[...target.querySelectorAll('.usd-position-legend span')].find(s=>/USD\/JPY/.test(s.textContent||''));
 if(legend)legend.innerHTML='<i class="lg-line price"></i>USD/JPY（右軸・52週）';
 const partial=[...target.querySelectorAll('.usd-position-note')].find(n=>/USD\/JPY価格線/.test(n.textContent||'')&&/未取得期間|確認済み/.test(n.textContent||''));
 if(partial)partial.textContent='USD/JPY価格線はCFTC基準日に対応する52週分の履歴価格を表示しています。';
 const source=target.querySelector('.usd-position-source');
 if(source&&!source.querySelector('[data-price52-source]')){
   const extra=document.createElement('span');extra.dataset.price52Source='1';extra.innerHTML='<br>52週価格補完：<a href="https://www.exchange-rates.org/exchange-rate-history/usd-jpy-2025" target="_blank" rel="noopener">Exchange-Rates.org 2025</a> / <a href="https://www.exchange-rates.org/exchange-rate-history/usd-jpy-2026" target="_blank" rel="noopener">2026</a>';
   source.appendChild(extra);
 }
}
let tries=0;const timer=setInterval(()=>{patch();if(++tries>=24)clearInterval(timer);},250);
const target=document.getElementById('usdjpy-positioning-content');
if(target){const observer=new MutationObserver(()=>setTimeout(patch,0));observer.observe(target,{childList:true,subtree:true});}
document.addEventListener('click',e=>{if(e.target.closest('.usd-position-range button[data-weeks]'))setTimeout(patch,30);});
})();
